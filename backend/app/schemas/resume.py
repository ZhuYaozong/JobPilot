from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ResumeCreate(BaseModel):
    title: str
    raw_text: str
    content_hash: str
    source_file_url: str | None = None
    source_type: str = "upload"


class ResumeUpdate(BaseModel):
    title: str | None = None
    raw_text: str | None = None
    source_file_url: str | None = None
    source_type: str | None = None
    content_hash: str | None = None


class ResumeListItem(BaseModel):
    id: int
    title: str
    source_type: str
    parse_status: str
    content_hash: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ResumeRead(ResumeListItem):
    source_file_url: str | None
    raw_text: str
    parsed_json: dict[str, Any] | None
