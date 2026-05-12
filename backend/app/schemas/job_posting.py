from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class JobPostingCreate(BaseModel):
    company_name: str
    job_title: str
    jd_text: str
    city: str | None = None
    source_url: str | None = None
    status: str = "active"


class JobPostingUpdate(BaseModel):
    company_name: str | None = None
    job_title: str | None = None
    city: str | None = None
    source_url: str | None = None
    jd_text: str | None = None
    status: str | None = None


class JobPostingListItem(BaseModel):
    id: int
    company_name: str
    job_title: str
    city: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobPostingRead(JobPostingListItem):
    source_url: str | None
    jd_text: str
    parsed_json: dict[str, Any] | None


class JobURLFetchRequest(BaseModel):
    url: str


class JobURLFetchPreview(BaseModel):
    """Preview-only payload from POST /jobs/fetch-from-url — nothing is
    persisted yet. The frontend uses this to pre-fill the create form; the
    user then submits a regular POST /jobs to save."""

    jd_text: str
    title: str | None
    company_hint: str | None
    city_hint: str | None
    source_url: str
