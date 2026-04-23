from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ArtifactFeedbackEvent(Base):
    __tablename__ = "artifact_feedback_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    generated_artifact_id: Mapped[int] = mapped_column(
        ForeignKey("generated_artifacts.id"),
        index=True,
    )
    feedback_type: Mapped[str] = mapped_column(String(50))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
