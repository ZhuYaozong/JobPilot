from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ApplicationTransitionRequest(BaseModel):
    target_stage: str
    next_action: str | None = None
    next_action_at: datetime | None = None
    notes: str | None = None
    event_at: datetime | None = None
    operator_type: str = "user"
    payload_json: dict[str, Any] | None = None
    note: str | None = None


class ApplicationEventListItem(BaseModel):
    id: int
    application_record_id: int
    event_type: str
    from_stage: str | None
    to_stage: str | None
    event_at: datetime | None
    operator_type: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApplicationEventRead(ApplicationEventListItem):
    payload_json: dict[str, Any] | None
    note: str | None
