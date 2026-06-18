"""
Semantic clustering via pgvector cosine similarity.

Strategy:
1. Fetch all articles from the last 24h that have embeddings and are not yet clustered.
2. For each unclustered article, find neighbors within cosine similarity threshold.
3. Groups of >= MIN_CLUSTER_SIZE form a cluster candidate.
4. Assign cluster_id to all members. Mark representative (highest embedding density).

This is a greedy single-pass clustering — not k-means. Fast enough for daily batch volumes
(hundreds of articles). Not optimal for very large corpora — revisit if volume exceeds 10k/day.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.article import Article
from app.models.synthesis import Synthesis

log = logging.getLogger(__name__)
settings = get_settings()


async def cluster_recent_articles(
    db: AsyncSession,
    hours: int = 24,
) -> list[int]:
    """
    Cluster articles from the last N hours by semantic similarity.

    Returns list of Synthesis IDs created.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    # Fetch unclustered, embedded articles
    result = await db.execute(
        select(Article)
        .where(
            Article.ingested_at >= cutoff,
            Article.embedding.is_not(None),
            Article.cluster_id.is_(None),
        )
        .order_by(Article.ingested_at.desc())
    )
    articles: list[Article] = list(result.scalars().all())

    if not articles:
        log.info("no unclustered articles to process")
        return []

    log.info("clustering %d articles from last %dh", len(articles), hours)

    assigned: set[int] = set()
    created_synthesis_ids: list[int] = []

    for anchor in articles:
        if anchor.id in assigned:
            continue

        # pgvector cosine similarity query
        # Convert embedding to pgvector '[f1,f2,...]' format — numpy str() is space-separated, not parseable
        emb_list = anchor.embedding.tolist() if hasattr(anchor.embedding, 'tolist') else list(anchor.embedding)
        anchor_vec_str = '[' + ','.join(str(x) for x in emb_list) + ']'
        neighbors_result = await db.execute(
            text(
                """
                SELECT id, 1 - (embedding <=> :anchor_vec) AS similarity
                FROM articles
                WHERE
                    id != :anchor_id
                    AND ingested_at >= :cutoff
                    AND embedding IS NOT NULL
                    AND cluster_id IS NULL
                    AND 1 - (embedding <=> :anchor_vec) >= :threshold
                ORDER BY similarity DESC
                LIMIT 50
                """
            ),
            {
                "anchor_vec": anchor_vec_str,
                "anchor_id": anchor.id,
                "cutoff": cutoff,
                "threshold": settings.cluster_similarity_threshold,
            },
        )
        neighbor_rows = neighbors_result.fetchall()

        cluster_ids = [anchor.id] + [row.id for row in neighbor_rows]

        if len(cluster_ids) < settings.cluster_min_articles:
            continue

        avg_sim = (
            sum(row.similarity for row in neighbor_rows) / len(neighbor_rows)
            if neighbor_rows
            else 1.0
        )

        # Create placeholder Synthesis — text filled by synthesize worker
        synthesis = Synthesis(
            theme="(pending synthesis)",
            digest_text="",
            article_count=len(cluster_ids),
            avg_similarity=avg_sim,
            window_start=cutoff,
            window_end=datetime.now(timezone.utc),
        )
        db.add(synthesis)
        await db.flush()

        # Assign cluster membership
        for art_id in cluster_ids:
            await db.execute(
                text(
                    "UPDATE articles SET cluster_id = :cid WHERE id = :aid"
                ),
                {"cid": synthesis.id, "aid": art_id},
            )
            assigned.add(art_id)

        # Mark representative = anchor article
        await db.execute(
            text(
                "UPDATE articles SET is_cluster_representative = TRUE WHERE id = :aid"
            ),
            {"aid": anchor.id},
        )

        # Propagate framework_release flag to cluster
        framework_members_result = await db.execute(
            text(
                "SELECT COUNT(*) FROM articles WHERE cluster_id = :cid AND is_framework_release = TRUE"
            ),
            {"cid": synthesis.id},
        )
        framework_count = framework_members_result.scalar() or 0
        if framework_count > 0:
            synthesis.is_framework_release = True

        created_synthesis_ids.append(synthesis.id)

    await db.commit()
    log.info("created %d clusters", len(created_synthesis_ids))
    return created_synthesis_ids
