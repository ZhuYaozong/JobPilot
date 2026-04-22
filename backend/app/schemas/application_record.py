from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ApplicationRecordCreate(BaseModel):
    resume_id: int
    job_posting_id: int
    current_stage: str = "saved"
    apply_channel: str | None = None
    applied_at: datetime | None = None
    next_action: str | None = None
    next_action_at: datetime | None = None
    notes: str | None = None


class ApplicationRecordUpdate(BaseModel):
    current_stage: str | None = None
    apply_channel: str | None = None
    applied_at: datetime | None = None
    next_action: str | None = None
    next_action_at: datetime | None = None
    notes: str | None = None


class ApplicationRecordListItem(BaseModel):
    id: int
    resume_id: int
    job_posting_id: int
    current_stage: str
    next_action: str | None
    next_action_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApplicationRecordRead(ApplicationRecordListItem):
    apply_channel: str | None
    applied_at: datetime | None
    notes: str | None
