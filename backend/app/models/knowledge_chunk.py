from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import settings
from app.db.base import Base


class KnowledgeChunk(Base):
    """A single embedded slice of a knowledge document.

    Designed for fast user-scoped vector search:
    - ``user_id`` is denormalised from the parent document so the search
      query can filter on a single column before the ANN scan.
    - ``embedding`` is a fixed-dimension pgvector column; the dim comes
      from settings.embedding_dimensions at module import time, so changing
      the embedding model requires a migration (intentional — we don't
      want silent dim mismatches at runtime).
    """

    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(settings.embedding_dimensions),
    )
    # Position in the source document — used to show "原文片段" with a bit
    # of surrounding context when rendering hits in the assistant chat.
    char_start: Mapped[int] = mapped_column(Integer)
    char_end: Mapped[int] = mapped_column(Integer)
    extra_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
