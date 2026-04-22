from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GeneratedArtifact(Base):
    __tablename__ = "generated_artifacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    artifact_type: Mapped[str] = mapped_column(String(50))
    resume_id: Mapped[int | None] = mapped_column(ForeignKey("resumes.id"), index=True)
    job_posting_id: Mapped[int | None] = mapped_column(
        ForeignKey("job_postings.id"),
        index=True,
    )
    application_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("application_records.id"),
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255))
    content_text: Mapped[str | None] = mapped_column(Text)
    content_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(50), server_default="draft")
    generator_type: Mapped[str] = mapped_column(String(50), server_default="manual")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
