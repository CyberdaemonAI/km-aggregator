"""
Synthesize worker — full daily pipeline:
  1. Cluster embedded articles by semantic similarity (pgvector cosine)
  2. Generate theme + digest for each cluster (Ollama llama3.3:70b)
  3. Scan for framework release signals
  4. Assemble Mattermost digest and send
  5. Write major discoveries to prom-memory

Runs once daily at 07:00 UTC (configured via APScheduler in main.py).
Can also be triggered manually via POST /digest/trigger.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.models.article import Article
from app.models.synthesis import Synthesis
from app.services import clustering as cluster_svc
from app.services import mattermost as mm_svc
from app.services import prom_memory as pm_svc
from app.services import synthesis as synth_svc

log = logging.getLogger(__name__)
settings = get_settings()

# Threshold for writing a cluster to prom-memory (article count)
PROM_MEMORY_MIN_ARTICLES = 5


async def run_synthesize() -> dict:
    """
    Full synthesis pipeline run.

    Returns stats dict.
    """
    stats = {
        "clusters_created": 0,
        "clusters_synthesized": 0,
        "framework_releases_found": 0,
        "prom_memory_writes": 0,
        "digest_sent": False,
        "errors": 0,
    }

    async with AsyncSessionLocal() as db:
        # 1. Cluster recent articles
        cluster_ids: list[int] = []  # default if clustering throws
        try:
            cluster_ids = await cluster_svc.cluster_recent_articles(db, hours=24)
            stats["clusters_created"] = len(cluster_ids)
            log.info("created %d clusters", len(cluster_ids))
        except Exception as exc:
            log.error("clustering failed: %s", exc)
            stats["errors"] += 1

        # 2. Synthesize each new cluster
        for cid in cluster_ids:
            try:
                result = await db.execute(
                    select(Synthesis).where(Synthesis.id == cid).limit(1)
                )
                cluster = result.scalar_one_or_none()
                if not cluster:
                    continue

                articles_result = await db.execute(
                    select(Article).where(Article.cluster_id == cid)
                )
                articles = list(articles_result.scalars().all())

                ok = await synth_svc.synthesize_cluster(cluster, articles, db)
                if ok:
                    stats["clusters_synthesized"] += 1

                    # Write significant clusters to prom-memory
                    if (
                        cluster.is_framework_release
                        or cluster.article_count >= PROM_MEMORY_MIN_ARTICLES
                    ):
                        wrote = await pm_svc.write_cluster_synthesis(cluster)
                        if wrote:
                            cluster.prom_memory_written = True
                            stats["prom_memory_writes"] += 1
                            await db.commit()

            except Exception as exc:
                log.error("synthesis failed for cluster %d: %s", cid, exc)
                stats["errors"] += 1

        # 3. Framework release scan (runs across last 48h, not just new clusters)
        try:
            flagged_ids = await synth_svc.scan_for_framework_releases(db)
            stats["framework_releases_found"] = len(flagged_ids)

            # Write each framework release to prom-memory + send alert
            for art_id in flagged_ids:
                art_result = await db.execute(
                    select(Article).where(Article.id == art_id).limit(1)
                )
                art = art_result.scalar_one_or_none()
                if art and not art.prom_memory_written:
                    wrote = await pm_svc.write_framework_release(art)
                    if wrote:
                        art.prom_memory_written = True
                        stats["prom_memory_writes"] += 1

                    alert_msg = (
                        f":warning: **Framework Release Detected**: {art.title}\n"
                        f"Source: {art.url}"
                    )
                    await mm_svc.send_alert(alert_msg)

            if flagged_ids:
                await db.commit()

        except Exception as exc:
            log.error("framework release scan failed: %s", exc)
            stats["errors"] += 1

        # 4. Build and send daily digest
        try:
            digest = await synth_svc.build_daily_digest(db, hours=24)
            if digest:
                sent = await mm_svc.send_digest(digest)
                stats["digest_sent"] = sent

                if sent:
                    # Mark all clusters in this digest as sent
                    from datetime import timedelta
                    from sqlalchemy import update

                    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
                    await db.execute(
                        __import__("sqlalchemy")
                        .update(Synthesis)
                        .where(
                            Synthesis.created_at >= cutoff,
                            Synthesis.mattermost_sent.is_(False),
                        )
                        .values(
                            mattermost_sent=True,
                            mattermost_sent_at=datetime.now(timezone.utc),
                        )
                    )
                    await db.commit()
            else:
                log.info("no clusters to digest — skipping Mattermost")

        except Exception as exc:
            log.error("digest delivery failed: %s", exc)
            stats["errors"] += 1

    log.info("synthesize complete: %s", stats)
    return stats
