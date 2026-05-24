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
    # AI 草稿模式可以一次写入结构化结果,避免落库后再触发一次 LLM 解析。
    parsed_json: dict[str, Any] | None = None


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
    """POST /jobs/fetch-from-url 返回的预览对象。

    此时不会写数据库；前端只用它预填创建表单，用户确认后再走常规 POST /jobs 保存。
    """

    jd_text: str
    title: str | None
    company_hint: str | None
    city_hint: str | None
    source_url: str
