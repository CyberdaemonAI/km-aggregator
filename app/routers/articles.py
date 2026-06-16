"""
Article endpoints.

GET /articles              — paginated article list with filters
GET /articles/{id}         — single article detail
GET /articles/search       — semantic search via pgvector
GET /articles/frameworks   — framework release flagged articles
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.models.article import Article

log = logging.getLogger(__name__)
router = APIRouter(prefix="/articles", tags=["articles"])
settings = get_settings()


class ArticleResponse(BaseModel):
    id: int
    url: str
    title: str
    summary: str | None
    author: str | None
    category: str | None
    source_type: str
    published_at: datetime | None
    ingested_at: datetime
    is_framework_release: bool
    cluster_id: int | None
    processed: bool

    class Config:
        from_attributes = True


class SearchResult(BaseModel):
    article: ArticleResponse
    similarity: float


@router.get("/", response_model=list[ArticleResponse])
async def list_articles(
    category: str | None = Query(None),
    source_type: str | None = Query(None),
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[Article]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    q = select(Article).where(Article.ingested_at >= cutoff)

    if category:
        q = q.where(Article.category == category)
    if source_type:
        q = q.where(Article.source_type == source_type)

    q = q.order_by(Article.ingested_at.desc()).limit(limit).offset(offset)
    result = await db.execute(q)
    return list(result.scalars().all())


@router.get("/frameworks", response_model=list[ArticleResponse])
async def list_framework_releases(
    hours: int = Query(168, ge=1, le=720),
    db: AsyncSession = Depends(get_db),
) -> list[Article]:
    """Articles flagged as framework/standards releases."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    result = await db.execute(
        select(Article)
        .where(
            Article.ingested_at >= cutoff,
            Article.is_framework_release.is_(True),
        )
        .order_by(Article.framework_release_flagged_at.desc())
        .limit(100)
    )
    return list(result.scalars().all())


@router.get("/search", response_model=list[SearchResult])
async def semantic_search(
    q: str = Query(..., min_length=3),
    top_k: int = Query(10, ge=1, le=50),
    category: str | None = Query(None),
    hours: int = Query(168, ge=1, le=720),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """
    Semantic search across articles via pgvector cosine similarity.

    Embeds the query string and finds nearest neighbors in article space.
    """
    from app.services.embeddings import embed_text

    embedding = await embed_text(q)
    if not embedding:
        raise HTTPException(status_code=503, detail="embedding service unavailable")

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    cat_filter = "AND category = :category" if category else ""

    rows = await db.execute(
        text(
            f"""
            SELECT id, 1 - (embedding <=> :query_vec) AS similarity
            FROM articles
            WHERE
                ingested_at >= :cutoff
                AND embedding IS NOT NULL
                {cat_filter}
            ORDER BY embedding <=> :query_vec
            LIMIT :top_k
            """
        ),
        {
            "query_vec": str(embedding),
            "cutoff": cutoff,
            "top_k": top_k,
            **({"category": category} if category else {}),
        },
    )
    rows = rows.fetchall()

    results = []
    for row in rows:
        art_result = await db.execute(
            select(Article).where(Article.id == row.id).limit(1)
        )
        art = art_result.scalar_one_or_none()
        if art:
            results.append({"article": art, "similarity": round(float(row.similarity), 4)})

    return results


@router.get("/{article_id}", response_model=ArticleResponse)
async def get_article(article_id: int, db: AsyncSession = Depends(get_db)) -> Article:
    result = await db.execute(
        select(Article).where(Article.id == article_id).limit(1)
    )
    art = result.scalar_one_or_none()
    if not art:
        raise HTTPException(status_code=404, detail="article not found")
    return art
