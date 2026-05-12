from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class KnowledgeDocument(Base):
    """A single uploaded document inside a knowledge base.

    The document stores both the original raw text (for re-chunking / detail
    view) and a denormalised user_id so the chunks table can filter on a
    single column without joining. Status drives the indexing state machine
    (slice 7'c2 fills it in):

        pending -> parsing -> ready
                          \\-> failed
    """

    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    knowledge_base_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        index=True,
    )
    title: Mapped[str] = mapped_column(String(512))
    # "pdf" | "docx" | "markdown" | "text" | "manual" (typed in by user).
    source_type: Mapped[str] = mapped_column(String(50))
    source_url: Mapped[str | None] = mapped_column(String(1024))
    raw_text: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    extra_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    chunk_count: Mapped[int] = mapped_column(Integer, server_default="0")
    # See class docstring; default starts at pending so the indexing worker
    # (7'c2) can pick it up.
    status: Mapped[str] = mapped_column(String(50), server_default="pending")
    error_detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
