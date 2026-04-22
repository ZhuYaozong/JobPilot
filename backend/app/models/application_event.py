from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ApplicationEvent(Base):
    __tablename__ = "application_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_record_id: Mapped[int] = mapped_column(
        ForeignKey("application_records.id"),
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(50))
    from_stage: Mapped[str | None] = mapped_column(String(50))
    to_stage: Mapped[str | None] = mapped_column(String(50))
    event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    operator_type: Mapped[str] = mapped_column(String(50), server_default="user")
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
