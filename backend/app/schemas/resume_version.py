from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ResumeVersionCreate(BaseModel):
    resume_id: int
    version_no: int
    version_label: str
    content: str
    job_posting_id: int | None = None
    content_format: str = "markdown"
    source_type: str = "manual"
    change_summary: str | None = None
    is_active: bool = True


class ResumeVersionUpdate(BaseModel):
    job_posting_id: int | None = None
    version_no: int | None = None
    version_label: str | None = None
    content: str | None = None
    content_format: str | None = None
    source_type: str | None = None
    change_summary: str | None = None
    is_active: bool | None = None


class ResumeVersionListItem(BaseModel):
    id: int
    resume_id: int
    job_posting_id: int | None
    version_no: int
    version_label: str
    content_format: str
    source_type: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ResumeVersionRead(ResumeVersionListItem):
    content: str
    change_summary: str | None
