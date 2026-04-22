"""Pydantic schemas will live here when the API grows."""
from app.schemas.job_posting import (
    JobPostingCreate,
    JobPostingListItem,
    JobPostingRead,
    JobPostingUpdate,
)
from app.schemas.resume import ResumeCreate, ResumeListItem, ResumeRead, ResumeUpdate

__all__ = [
    "JobPostingCreate",
    "JobPostingListItem",
    "JobPostingRead",
    "JobPostingUpdate",
    "ResumeCreate",
    "ResumeListItem",
    "ResumeRead",
    "ResumeUpdate",
]
