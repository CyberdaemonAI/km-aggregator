"""
Configuration — all values from environment variables.
No secrets in code. No internal URLs hardcoded.

Copy .env.example to .env and fill in values for local dev.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Database ───────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://km:km@localhost:5432/km"

    # ── Inference (Ollama on Thor — self-hosted, no paid API) ──────────────────
    ollama_base_url: str = "http://localhost:11434"
    embed_model: str = "nomic-embed-text"
    synthesis_model: str = "llama3.3:70b"
    ollama_timeout: int = 120  # seconds

    # ── Notifications ──────────────────────────────────────────────────────────
    mattermost_webhook_url: str = ""  # required for digest delivery

    # ── prom-memory integration ────────────────────────────────────────────────
    prom_memory_url: str = ""  # POST /memory when major discovery found
    prom_memory_enabled: bool = False  # off by default; set to true with URL

    # ── Ingest tuning ─────────────────────────────────────────────────────────
    max_items_per_feed: int = 25        # cap RSS backlog per poll
    max_videos_per_channel: int = 10    # cap YouTube videos per poll
    youtube_transcript_max_chars: int = 16000

    # ── Clustering + synthesis ────────────────────────────────────────────────
    cluster_similarity_threshold: float = 0.85  # pgvector cosine threshold
    cluster_min_articles: int = 3               # min articles to synthesize
    digest_schedule_utc: str = "07:00"          # daily digest time

    # ── Scheduler ─────────────────────────────────────────────────────────────
    ingest_interval_minutes: int = 120   # 2h polling cycle
    embed_interval_minutes: int = 30     # embed worker catches up every 30m
    digest_interval_hours: int = 24      # daily synthesis

    # ── App ────────────────────────────────────────────────────────────────────
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"
    environment: str = "development"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
