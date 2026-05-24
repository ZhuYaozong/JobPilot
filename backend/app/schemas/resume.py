from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ResumeCreate(BaseModel):
    title: str
    raw_text: str
    content_hash: str
    source_file_url: str | None = None
    source_type: str = "upload"
    # AI 草稿模式可以一次写入结构化结果与解析状态,避免落库后再触发一次 LLM 解析。
    # 普通 paste 模式不传,保留服务端默认行为(parse_status="pending")。
    parsed_json: dict[str, Any] | None = None
    parse_status: str | None = None


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
