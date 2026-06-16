"""
prom-memory integration for km-aggregator.

When a major discovery is made — new framework release, significant
threat actor campaign, major breach — write a structured memory entry
to prom-memory via its REST API.

This is a one-way write. km-aggregator does not read from prom-memory.

prom-memory endpoint configured via PROM_MEMORY_URL env var.
PROM_MEMORY_ENABLED must be true (default: false — explicit opt-in).
"""

import logging
from datetime import datetime, timezone

import httpx

from app.config import get_settings
from app.models.article import Article
from app.models.synthesis import Synthesis

log = logging.getLogger(__name__)
settings = get_settings()


async def write_framework_release(article: Article) -> bool:
    """
    Write a framework release discovery to prom-memory.

    Called when scan_for_framework_releases() flags an article.
    """
    if not settings.prom_memory_enabled or not settings.prom_memory_url:
        return False

    content = (
        f"Framework release detected by km-aggregator: {article.title}. "
        f"Source: {article.url}. "
        f"Category: {article.category or 'unknown'}. "
        f"Detected at: {datetime.now(timezone.utc).isoformat()}"
    )

    return await _write_memory(
        content=content,
        tags=["km-aggregator", "framework-release", article.category or "unknown"],
        importance="high",
    )


async def write_cluster_synthesis(cluster: Synthesis) -> bool:
    """
    Write a significant cluster synthesis to prom-memory.

    Called for clusters with is_framework_release=True or article_count >= 5.
    """
    if not settings.prom_memory_enabled or not settings.prom_memory_url:
        return False

    content = (
        f"km-aggregator cluster synthesis ({cluster.article_count} sources): "
        f"{cluster.theme}. "
        f"{cluster.digest_text}"
    )

    importance = "high" if cluster.is_framework_release else "medium"

    return await _write_memory(
        content=content,
        tags=["km-aggregator", "synthesis", cluster.category or "unknown"],
        importance=importance,
    )


async def _write_memory(
    content: str,
    tags: list[str],
    importance: str = "medium",
) -> bool:
    """
    POST a memory entry to prom-memory REST API.

    Expected request format: {"content": str, "tags": list[str], "importance": str}
    Adjust if prom-memory schema differs.
    """
    url = f"{settings.prom_memory_url.rstrip('/')}/memory"
    payload = {
        "content": content,
        "tags": tags,
        "importance": importance,
        "source": "km-aggregator",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            log.info("prom-memory write OK: %s", content[:60])
            return True
    except httpx.ConnectError:
        log.warning(
            "prom-memory unreachable at %s — skipping write", settings.prom_memory_url
        )
        return False
    except Exception as exc:
        log.warning("prom-memory write failed: %s", exc)
        return False
