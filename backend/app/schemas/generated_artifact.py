from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class GeneratedArtifactCreate(BaseModel):
    artifact_type: str
    title: str
    resume_id: int | None = None
    job_posting_id: int | None = None
    application_record_id: int | None = None
    content_text: str | None = None
    content_json: dict[str, Any] | None = None
    status: str = "draft"
    generator_type: str = "manual"


class GeneratedArtifactUpdate(BaseModel):
    artifact_type: str | None = None
    resume_id: int | None = None
    job_posting_id: int | None = None
    application_record_id: int | None = None
    title: str | None = None
    content_text: str | None = None
    content_json: dict[str, Any] | None = None
    status: str | None = None
    generator_type: str | None = None


class GeneratedArtifactListItem(BaseModel):
    id: int
    artifact_type: str
    resume_id: int | None
    job_posting_id: int | None
    application_record_id: int | None
    title: str
    status: str
    generator_type: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GeneratedArtifactRead(GeneratedArtifactListItem):
    content_text: str | None
    content_json: dict[str, Any] | None
