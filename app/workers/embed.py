"""
Embed worker — generates pgvector embeddings for articles that have content but no embedding.

Runs on a shorter interval than ingest (default: every 30 minutes).
Processes articles in batches to avoid overloading the Ollama endpoint.

Embedding model: nomic-embed-text via Ollama (768 dimensions).
After embedding, articles are eligible for clustering.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models.article import Article
from app.services.embeddings import embed_text

log = logging.getLogger(__name__)
settings = get_settings()

BATCH_SIZE = 20  # articles per worker run to avoid Ollama overload


async def run_embed() -> dict:
    """
    Generate embeddings for all unembedded articles with content.

    Returns stats: {processed, skipped_no_content, errors}
    """
    stats = {"processed": 0, "skipped_no_content": 0, "errors": 0}

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Article)
            .where(
                Article.embedding.is_(None),
                Article.content.is_not(None),
            )
            .order_by(Article.ingested_at.asc())
            .limit(BATCH_SIZE)
        )
        articles: list[Article] = list(result.scalars().all())

        if not articles:
            log.debug("no articles to embed")
            return stats

        log.info("embedding %d articles", len(articles))

        for art in articles:
            text_to_embed = _build_embed_input(art)
            if not text_to_embed:
                stats["skipped_no_content"] += 1
                continue

            try:
                embedding = await embed_text(text_to_embed)
                if embedding:
                    art.embedding = embedding
                    art.embedded_at = datetime.now(timezone.utc)
                    stats["processed"] += 1
                else:
                    stats["errors"] += 1
            except Exception as exc:
                log.warning("embed failed for article %d: %s", art.id, exc)
                stats["errors"] += 1

        await db.commit()

    log.info(
        "embed complete: %d processed, %d skipped, %d errors",
        stats["processed"],
        stats["skipped_no_content"],
        stats["errors"],
    )
    return stats


def _build_embed_input(art: Article) -> str:
    """
    Build the text input for embedding.

    Strategy: title + first 2000 chars of content.
    Title is weighted by repetition (simple but effective).
    """
    parts = []
    if art.title:
        parts.append(art.title.strip())
        parts.append(art.title.strip())  # repeat title to weight it

    content = art.content or art.summary or ""
    if content:
        parts.append(content[:2000])

    return " ".join(parts).strip()
