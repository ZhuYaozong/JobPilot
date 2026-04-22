from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MatchResult(Base):
    __tablename__ = "match_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id"), index=True)
    job_posting_id: Mapped[int] = mapped_column(
        ForeignKey("job_postings.id"),
        index=True,
    )
    overall_score: Mapped[float] = mapped_column(Float)
    strengths: Mapped[list[Any] | None] = mapped_column(JSONB)
    weaknesses: Mapped[list[Any] | None] = mapped_column(JSONB)
    missing_keywords: Mapped[list[Any] | None] = mapped_column(JSONB)
    suggestions: Mapped[list[Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
