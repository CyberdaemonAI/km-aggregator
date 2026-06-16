"""
Digest endpoints.

GET  /digest/latest     — fetch most recent synthesis clusters
POST /digest/trigger    — manually trigger full synthesize pipeline
GET  /digest/status     — last run stats
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.synthesis import Synthesis

log = logging.getLogger(__name__)
router = APIRouter(prefix="/digest", tags=["digest"])

# In-memory last-run tracker (reset on restart — not persisted)
_last_run: dict = {}


class SynthesisResponse(BaseModel):
    id: int
    theme: str
    digest_text: str
    category: str | None
    article_count: int
    is_framework_release: bool
    mattermost_sent: bool
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/latest", response_model=list[SynthesisResponse])
async def get_latest_digest(
    hours: int = 24,
    db: AsyncSession = Depends(get_db),
) -> list[Synthesis]:
    """Return synthesis clusters from the last N hours."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    result = await db.execute(
        select(Synthesis)
        .where(Synthesis.created_at >= cutoff)
        .order_by(Synthesis.is_framework_release.desc(), Synthesis.article_count.desc())
    )
    return list(result.scalars().all())


@router.post("/trigger")
async def trigger_synthesize(
    background_tasks: BackgroundTasks,
) -> dict:
    """
    Manually trigger the full synthesis pipeline (cluster + synthesize + digest).

    Runs in background — returns immediately with job ID.
    Check /digest/status for result.
    """
    from app.workers.synthesize import run_synthesize

    if _last_run.get("running"):
        raise HTTPException(status_code=409, detail="synthesis already running")

    _last_run["running"] = True
    _last_run["started_at"] = datetime.now(timezone.utc).isoformat()

    async def _run() -> None:
        try:
            stats = await run_synthesize()
            _last_run.update(stats)
        finally:
            _last_run["running"] = False
            _last_run["completed_at"] = datetime.now(timezone.utc).isoformat()

    background_tasks.add_task(_run)
    return {"status": "triggered", "started_at": _last_run["started_at"]}


@router.get("/status")
async def get_status() -> dict:
    """Return last synthesis run stats."""
    return _last_run or {"status": "no runs yet"}
