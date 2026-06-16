"""
Ingest worker — polls RSS feeds and YouTube channels, deduplicates, stores raw articles.

Runs on a configurable interval (default: every 2 hours).
Does NOT generate embeddings or synthesize — those are handled by embed.py and synthesize.py.

Dedup strategy: content_hash on (normalized URL + title). UNIQUE constraint on url column.
Same story from multiple sources: stores once, earliest ingested_at wins.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.feeds_config import FEEDS, YOUTUBE_CHANNELS
from app.models.article import Article
from app.models.feed import Feed
from app.services import rss as rss_svc
from app.services import youtube as yt_svc

log = logging.getLogger(__name__)
settings = get_settings()


async def run_ingest() -> dict:
    """
    Full ingest cycle: RSS + YouTube.

    Returns stats dict: {rss_fetched, youtube_fetched, new_articles, skipped_dupes}
    """
    stats = {
        "rss_fetched": 0,
        "youtube_fetched": 0,
        "new_articles": 0,
        "skipped_dupes": 0,
        "errors": 0,
    }

    async with AsyncSessionLocal() as db:
        await _ingest_rss(db, stats)
        await _ingest_youtube(db, stats)

    log.info(
        "ingest complete: %d new articles, %d dupes skipped, %d errors",
        stats["new_articles"],
        stats["skipped_dupes"],
        stats["errors"],
    )
    return stats


async def _ingest_rss(db: AsyncSession, stats: dict) -> None:
    """Poll all active RSS feeds."""
    for feed_cfg in FEEDS:
        if feed_cfg["type"] != "rss":
            continue

        feed = await _ensure_feed(db, feed_cfg)
        if not feed:
            continue

        try:
            entries = await rss_svc.fetch_feed(
                feed_cfg["url"], max_items=settings.max_items_per_feed
            )
            stats["rss_fetched"] += len(entries)

            for entry in entries:
                added = await _upsert_article(
                    db,
                    url=entry["url"],
                    title=entry["title"],
                    content=entry.get("content"),
                    author=entry.get("author"),
                    published_at=entry.get("published_at"),
                    content_hash=entry.get("content_hash"),
                    source_type="rss",
                    category=feed_cfg["category"],
                    feed_id=feed.id,
                )
                if added:
                    stats["new_articles"] += 1
                else:
                    stats["skipped_dupes"] += 1

            feed.last_polled_at = datetime.now(timezone.utc)
            feed.error_count = 0
            await db.commit()

        except Exception as exc:
            log.error("RSS ingest error [%s]: %s", feed_cfg["url"], exc)
            feed.error_count = (feed.error_count or 0) + 1
            feed.last_error = str(exc)[:500]
            await db.commit()
            stats["errors"] += 1


async def _ingest_youtube(db: AsyncSession, stats: dict) -> None:
    """Poll all YouTube channels and fetch transcripts for new videos."""
    for ch in YOUTUBE_CHANNELS:
        feed_cfg = {
            "name": ch["name"],
            "url": f"https://www.youtube.com/feeds/videos.xml?channel_id={ch['channel_id']}",
            "type": "youtube",
            "category": ch["category"],
        }
        feed = await _ensure_feed(db, feed_cfg, channel_id=ch["channel_id"])
        if not feed:
            continue

        try:
            videos = await yt_svc.fetch_channel_videos(
                channel_id=ch["channel_id"],
                channel_name=ch["name"],
                max_videos=settings.max_videos_per_channel,
            )
            stats["youtube_fetched"] += len(videos)

            for video in videos:
                # Check if already ingested before fetching transcript
                existing = await db.execute(
                    select(Article).where(Article.url == video["url"]).limit(1)
                )
                if existing.scalar_one_or_none():
                    stats["skipped_dupes"] += 1
                    continue

                transcript = await yt_svc.fetch_transcript(
                    video["video_id"],
                    max_chars=settings.youtube_transcript_max_chars,
                )

                added = await _upsert_article(
                    db,
                    url=video["url"],
                    title=video["title"],
                    content=transcript,
                    author=ch["name"],
                    published_at=video.get("published_at"),
                    content_hash=None,
                    source_type="youtube",
                    category=ch["category"],
                    feed_id=feed.id,
                )
                if added:
                    stats["new_articles"] += 1
                else:
                    stats["skipped_dupes"] += 1

            feed.last_polled_at = datetime.now(timezone.utc)
            feed.error_count = 0
            await db.commit()

        except Exception as exc:
            log.error("YouTube ingest error [%s]: %s", ch["name"], exc)
            feed.error_count = (feed.error_count or 0) + 1
            feed.last_error = str(exc)[:500]
            await db.commit()
            stats["errors"] += 1


async def _ensure_feed(
    db: AsyncSession, cfg: dict, channel_id: str | None = None
) -> Feed | None:
    """Get or create a Feed row for a feed config dict."""
    result = await db.execute(
        select(Feed).where(Feed.url == cfg["url"]).limit(1)
    )
    feed = result.scalar_one_or_none()
    if feed:
        return feed

    try:
        feed = Feed(
            name=cfg["name"],
            url=cfg["url"],
            feed_type=cfg["type"],
            category=cfg["category"],
            channel_id=channel_id,
            active=True,
        )
        db.add(feed)
        await db.commit()
        await db.refresh(feed)
        log.info("created feed: %s", cfg["name"])
        return feed
    except Exception as exc:
        log.error("failed to create feed [%s]: %s", cfg["name"], exc)
        await db.rollback()
        return None


async def _upsert_article(
    db: AsyncSession,
    url: str,
    title: str,
    content: str | None,
    author: str | None,
    published_at: datetime | None,
    content_hash: str | None,
    source_type: str,
    category: str,
    feed_id: int,
) -> bool:
    """
    Insert article if URL not already present. Returns True if inserted, False if dupe.
    Uses PostgreSQL ON CONFLICT DO NOTHING for safe concurrent inserts.
    """
    stmt = (
        pg_insert(Article)
        .values(
            url=url,
            title=title,
            content=content,
            author=author,
            published_at=published_at,
            content_hash=content_hash,
            source_type=source_type,
            category=category,
            feed_id=feed_id,
            processed=False,
            ingested_at=datetime.now(timezone.utc),
        )
        .on_conflict_do_nothing(index_elements=["url"])
    )
    result = await db.execute(stmt)
    await db.flush()
    return (result.rowcount or 0) > 0
