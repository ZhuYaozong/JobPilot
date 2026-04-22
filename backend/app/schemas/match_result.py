from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class MatchResultCreate(BaseModel):
    resume_id: int
    job_posting_id: int
    overall_score: float
    strengths: list[Any] | None = None
    weaknesses: list[Any] | None = None
    missing_keywords: list[Any] | None = None
    suggestions: list[Any] | None = None


class MatchResultUpdate(BaseModel):
    overall_score: float | None = None
    strengths: list[Any] | None = None
    weaknesses: list[Any] | None = None
    missing_keywords: list[Any] | None = None
    suggestions: list[Any] | None = None


class MatchResultListItem(BaseModel):
    id: int
    resume_id: int
    job_posting_id: int
    overall_score: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MatchResultRead(MatchResultListItem):
    strengths: list[Any] | None
    weaknesses: list[Any] | None
    missing_keywords: list[Any] | None
    suggestions: list[Any] | None
