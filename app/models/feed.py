"""
Feed model — tracks RSS sources, YouTube channels, and watched URLs.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Feed(Base):
    __tablename__ = "feeds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    feed_type: Mapped[str] = mapped_column(
        Enum("rss", "youtube", "watched_url", name="feed_type_enum"),
        nullable=False,
    )
    category: Mapped[str] = mapped_column(
        Enum(
            "ai-security",
            "identity-iam",
            "threat-intel",
            "ai-llm",
            "architecture",
            "standards",
            "tools",
            name="category_enum",
        ),
        nullable=False,
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # YouTube-specific
    channel_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Tracking
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    articles: Mapped[list["Article"]] = relationship(  # noqa: F821
        "Article", back_populates="feed", lazy="dynamic"
    )

    def __repr__(self) -> str:
        return f"<Feed {self.name} ({self.feed_type}/{self.category})>"
