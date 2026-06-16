"""
RSS fetcher service.

Polls RSS/Atom feeds via feedparser. Normalizes entries into a dict
that maps cleanly to the Article model. Handles redirects, feed
errors, and empty/malformed feeds gracefully — logs warnings, never
raises to the caller.
"""

import hashlib
import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

import feedparser
import httpx

log = logging.getLogger(__name__)


def _normalize_url(url: str) -> str:
    """Strip UTM/tracking params to prevent same-article dedup failures."""
    STRIP_PARAMS = {
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "mc_cid", "mc_eid", "fbclid", "gclid", "ref", "source",
    }
    try:
        parsed = urlparse(url)
        params = {
            k: v for k, v in parse_qs(parsed.query).items()
            if k.lower() not in STRIP_PARAMS
        }
        clean = parsed._replace(query=urlencode(params, doseq=True))
        return urlunparse(clean)
    except Exception:
        return url


def _parse_date(entry: feedparser.FeedParserDict) -> datetime | None:
    """Extract published date from feed entry, return UTC datetime or None."""
    for attr in ("published", "updated", "created"):
        raw = entry.get(f"{attr}_parsed") or entry.get(attr)
        if raw is None:
            continue
        if hasattr(raw, "tm_year"):
            import time
            return datetime(*raw[:6], tzinfo=timezone.utc)
        if isinstance(raw, str):
            try:
                dt = parsedate_to_datetime(raw)
                return dt.astimezone(timezone.utc)
            except Exception:
                pass
    return None


def _content_hash(url: str, title: str) -> str:
    key = f"{_normalize_url(url)}||{title.strip().lower()}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


async def fetch_feed(feed_url: str, max_items: int = 25) -> list[dict]:
    """
    Fetch and parse an RSS/Atom feed.

    Returns a list of normalized article dicts:
        url, title, content, author, published_at, content_hash

    Never raises. Returns [] on any failure.
    """
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            resp = await client.get(
                feed_url,
                headers={"User-Agent": "km-aggregator/2.0 (+https://cyberdaemon.ai)"},
            )
            resp.raise_for_status()
            raw = resp.text
    except Exception as exc:
        log.warning("feed fetch failed [%s]: %s", feed_url, exc)
        return []

    parsed = feedparser.parse(raw)

    if parsed.bozo and not parsed.entries:
        log.warning("feed parse error [%s]: %s", feed_url, parsed.bozo_exception)
        return []

    results: list[dict] = []
    for entry in parsed.entries[:max_items]:
        url = entry.get("link") or entry.get("id") or ""
        if not url:
            continue
        url = _normalize_url(url)
        title = entry.get("title", "").strip() or "(no title)"

        # Best-effort content extraction
        content = ""
        if entry.get("content"):
            content = entry.content[0].get("value", "")
        elif entry.get("summary"):
            content = entry.get("summary", "")

        results.append(
            {
                "url": url,
                "title": title,
                "content": content,
                "author": entry.get("author") or entry.get("author_detail", {}).get("name"),
                "published_at": _parse_date(entry),
                "content_hash": _content_hash(url, title),
            }
        )

    log.info("fetched %d items from %s", len(results), feed_url)
    return results
