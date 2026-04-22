from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ResumeVersion(Base):
    __tablename__ = "resume_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id"), index=True)
    job_posting_id: Mapped[int | None] = mapped_column(
        ForeignKey("job_postings.id"),
        index=True,
    )
    version_no: Mapped[int] = mapped_column(Integer)
    version_label: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    content_format: Mapped[str] = mapped_column(String(50), server_default="markdown")
    source_type: Mapped[str] = mapped_column(String(50), server_default="manual")
    change_summary: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
