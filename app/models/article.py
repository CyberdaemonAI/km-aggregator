"""
Article model — stores ingested content with pgvector embeddings.

embedding column is VECTOR(768) — matches nomic-embed-text output dimension.
Cosine similarity on this column drives clustering and semantic search.
"""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Source tracking
    feed_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("feeds.id", ondelete="SET NULL"), nullable=True
    )
    source_type: Mapped[str] = mapped_column(
        Enum("rss", "youtube", "watched_url", name="source_type_enum"),
        nullable=False,
        default="rss",
    )

    # Content
    url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)  # raw body
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)  # synthesis output
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Classification
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Embeddings — pgvector VECTOR(768)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(768), nullable=True)
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Cluster membership
    cluster_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("synthesis.id", ondelete="SET NULL"), nullable=True
    )
    is_cluster_representative: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    # Framework release detection
    is_framework_release: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    framework_release_flagged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Pipeline state
    processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    prom_memory_written: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Metadata
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Relationships
    feed: Mapped["Feed"] = relationship("Feed", back_populates="articles")  # noqa: F821
    cluster: Mapped["Synthesis | None"] = relationship(  # noqa: F821
        "Synthesis", back_populates="articles"
    )

    def __repr__(self) -> str:
        return f"<Article {self.id}: {self.title[:60]}>"
