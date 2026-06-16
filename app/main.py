"""
km-aggregator — FastAPI app entry point.

Wires:
- FastAPI application with routers
- APScheduler for async background workers
- Database initialization on startup
- Health endpoint
"""

import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db
from app.routers import articles, digest, feeds
from app.workers.embed import run_embed
from app.workers.ingest import run_ingest
from app.workers.synthesize import run_synthesize

log = logging.getLogger(__name__)
settings = get_settings()

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    log.info("km-aggregator starting up")

    await init_db()

    # Schedule workers
    scheduler.add_job(
        run_ingest,
        trigger=IntervalTrigger(minutes=settings.ingest_interval_minutes),
        id="ingest",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        run_embed,
        trigger=IntervalTrigger(minutes=settings.embed_interval_minutes),
        id="embed",
        replace_existing=True,
        max_instances=1,
    )

    # Parse digest schedule: "07:00" -> hour=7, minute=0
    digest_hour, digest_minute = (
        int(x) for x in settings.digest_schedule_utc.split(":")
    )
    scheduler.add_job(
        run_synthesize,
        trigger=CronTrigger(hour=digest_hour, minute=digest_minute, timezone="UTC"),
        id="synthesize",
        replace_existing=True,
        max_instances=1,
    )

    scheduler.start()
    log.info(
        "scheduler started — ingest every %dm, embed every %dm, digest at %s UTC",
        settings.ingest_interval_minutes,
        settings.embed_interval_minutes,
        settings.digest_schedule_utc,
    )

    yield

    # Shutdown
    scheduler.shutdown(wait=False)
    log.info("km-aggregator shut down")


app = FastAPI(
    title="km-aggregator",
    description="AI security news aggregator with semantic clustering and framework release detection",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(feeds.router)
app.include_router(articles.router)
app.include_router(digest.router)


@app.get("/health")
async def health() -> dict:
    return {
        "ok": True,
        "version": "2.0.0",
        "scheduler_running": scheduler.running,
    }


@app.get("/")
async def root() -> dict:
    return {
        "service": "km-aggregator",
        "docs": "/docs",
        "health": "/health",
    }
