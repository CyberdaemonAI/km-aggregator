"""
Feed management endpoints.

GET  /feeds          — list all feeds with status
POST /feeds/add      — add a new feed (RSS URL or YouTube channel ID)
POST /feeds/{id}/toggle  — enable/disable a feed
DELETE /feeds/{id}   — remove a feed
"""

import logging
from datetime import datetime, timezone

import feedparser
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.feed import Feed

log = logging.getLogger(__name__)
router = APIRouter(prefix="/feeds", tags=["feeds"])


class FeedCreate(BaseModel):
    name: str
    url: str
    feed_type: str  # "rss" or "youtube"
    category: str
    channel_id: str | None = None

    @field_validator("feed_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in ("rss", "youtube", "watched_url"):
            raise ValueError("feed_type must be rss, youtube, or watched_url")
        return v

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        valid = {
            "ai-security", "identity-iam", "threat-intel",
            "ai-llm", "architecture", "standards", "tools",
        }
        if v not in valid:
            raise ValueError(f"category must be one of {sorted(valid)}")
        return v


class FeedResponse(BaseModel):
    id: int
    name: str
    url: str
    feed_type: str
    category: str
    active: bool
    last_polled_at: datetime | None
    error_count: int
    last_error: str | None

    class Config:
        from_attributes = True


@router.get("/", response_model=list[FeedResponse])
async def list_feeds(db: AsyncSession = Depends(get_db)) -> list[Feed]:
    result = await db.execute(select(Feed).order_by(Feed.category, Feed.name))
    return list(result.scalars().all())


@router.post("/add", response_model=FeedResponse, status_code=201)
async def add_feed(data: FeedCreate, db: AsyncSession = Depends(get_db)) -> Feed:
    # Check for duplicate
    existing = await db.execute(select(Feed).where(Feed.url == data.url).limit(1))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="feed URL already exists")

    # Validate RSS feed is live (YouTube channels skip this check)
    if data.feed_type == "rss":
        await _validate_rss(data.url)

    feed = Feed(
        name=data.name,
        url=data.url,
        feed_type=data.feed_type,
        category=data.category,
        channel_id=data.channel_id,
        active=True,
    )
    db.add(feed)
    await db.commit()
    await db.refresh(feed)
    log.info("added feed: %s (%s)", data.name, data.url)
    return feed


@router.post("/{feed_id}/toggle")
async def toggle_feed(feed_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    result = await db.execute(select(Feed).where(Feed.id == feed_id).limit(1))
    feed = result.scalar_one_or_none()
    if not feed:
        raise HTTPException(status_code=404, detail="feed not found")

    feed.active = not feed.active
    await db.commit()
    return {"id": feed_id, "active": feed.active}


@router.delete("/{feed_id}")
async def delete_feed(feed_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    result = await db.execute(select(Feed).where(Feed.id == feed_id).limit(1))
    feed = result.scalar_one_or_none()
    if not feed:
        raise HTTPException(status_code=404, detail="feed not found")

    await db.delete(feed)
    await db.commit()
    return {"deleted": feed_id}


async def _validate_rss(url: str) -> None:
    """Quick validation that URL returns parseable RSS/Atom."""
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
        parsed = feedparser.parse(resp.text)
        if parsed.bozo and not parsed.entries:
            raise HTTPException(
                status_code=422,
                detail=f"URL does not appear to be a valid RSS/Atom feed: {parsed.bozo_exception}",
            )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"feed validation failed: {exc}")
