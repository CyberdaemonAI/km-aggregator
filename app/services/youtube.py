"""
YouTube transcript fetcher.

Strategy:
1. Poll YouTube channel RSS feed (no API key required).
   URL: https://www.youtube.com/feeds/videos.xml?channel_id=<ID>
2. For each new video, run yt-dlp to fetch auto-generated VTT transcript.
   Flags: --skip-download --write-auto-sub --sub-lang en --sub-format vtt
3. Parse VTT into plain text: strip timestamps, deduplicate repeated captions.
4. Chunk to max_chars (default 16000 — ~4k tokens). Store as article content.

No audio is downloaded. No Whisper required for YouTube-hosted content.
For non-YouTube podcasts (mp3 RSS), see ingest worker — Whisper on GPU node.
"""

import asyncio
import logging
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import httpx

log = logging.getLogger(__name__)

YT_FEED_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"


async def fetch_channel_videos(
    channel_id: str,
    channel_name: str,
    max_videos: int = 10,
) -> list[dict]:
    """
    Fetch recent video entries from a YouTube channel RSS feed.

    Returns list of dicts: video_id, url, title, published_at, channel_name, channel_id
    """
    feed_url = YT_FEED_URL.format(channel_id=channel_id)
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
            resp = await client.get(feed_url)
            resp.raise_for_status()
            raw = resp.text
    except Exception as exc:
        log.warning("YouTube RSS fetch failed [%s / %s]: %s", channel_name, channel_id, exc)
        return []

    parsed = feedparser.parse(raw)
    results = []
    for entry in parsed.entries[:max_videos]:
        video_id = entry.get("yt_videoid") or ""
        url = entry.get("link", "")
        title = entry.get("title", "").strip()
        results.append(
            {
                "video_id": video_id,
                "url": url,
                "title": title,
                "channel_name": channel_name,
                "channel_id": channel_id,
                "published_at": _parse_yt_date(entry),
            }
        )

    log.info("found %d videos for channel %s", len(results), channel_name)
    return results


def _parse_yt_date(entry: feedparser.FeedParserDict) -> datetime | None:
    raw = entry.get("published_parsed") or entry.get("updated_parsed")
    if raw and hasattr(raw, "tm_year"):
        return datetime(*raw[:6], tzinfo=timezone.utc)
    return None


async def fetch_transcript(video_id: str, max_chars: int = 16000) -> str | None:
    """
    Fetch auto-generated VTT transcript for a YouTube video via yt-dlp.

    Writes to a temp directory, parses VTT to plain text, returns truncated string.
    Returns None if transcript unavailable or yt-dlp fails.
    """
    url = f"https://www.youtube.com/watch?v={video_id}"
    with tempfile.TemporaryDirectory() as tmpdir:
        cmd = [
            "yt-dlp",
            "--skip-download",
            "--write-auto-sub",
            "--sub-lang", "en",
            "--sub-format", "vtt",
            "--output", str(Path(tmpdir) / "%(id)s.%(ext)s"),
            "--quiet",
            "--no-warnings",
            url,
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
            if proc.returncode != 0:
                log.warning("yt-dlp failed [%s]: %s", video_id, stderr.decode()[:200])
                return None
        except asyncio.TimeoutError:
            log.warning("yt-dlp timed out for video %s", video_id)
            return None
        except FileNotFoundError:
            log.error("yt-dlp not found — install it: pip install yt-dlp")
            return None

        # Find the VTT file
        vtt_files = list(Path(tmpdir).glob("*.vtt"))
        if not vtt_files:
            log.debug("no VTT transcript available for video %s", video_id)
            return None

        vtt_text = vtt_files[0].read_text(encoding="utf-8", errors="replace")
        return _parse_vtt(vtt_text, max_chars=max_chars)


def _parse_vtt(vtt: str, max_chars: int = 16000) -> str:
    """
    Parse WebVTT format into plain text.

    - Strips timestamp lines (00:00:00.000 --> 00:00:00.000)
    - Strips HTML tags from captions
    - Deduplicates consecutive identical lines (YouTube auto-captions repeat heavily)
    - Truncates to max_chars
    """
    TIMESTAMP_RE = re.compile(
        r"^\d{2}:\d{2}:\d{2}\.\d{3}\s+-->\s+\d{2}:\d{2}:\d{2}\.\d{3}"
    )
    TAG_RE = re.compile(r"<[^>]+>")

    lines = []
    prev = ""
    for line in vtt.splitlines():
        line = line.strip()
        if not line or line.startswith("WEBVTT") or TIMESTAMP_RE.match(line):
            continue
        cleaned = TAG_RE.sub("", line).strip()
        if not cleaned or cleaned == prev:
            continue
        lines.append(cleaned)
        prev = cleaned

    text = " ".join(lines)
    return text[:max_chars]
