"""Pydantic schemas will live here when the API grows."""
from app.schemas.job_posting import (
    JobPostingCreate,
    JobPostingListItem,
    JobPostingRead,
    JobPostingUpdate,
)
from app.schemas.match_result import (
    MatchResultCreate,
    MatchResultListItem,
    MatchResultRead,
    MatchResultUpdate,
)
from app.schemas.resume import ResumeCreate, ResumeListItem, ResumeRead, ResumeUpdate

__all__ = [
    "JobPostingCreate",
    "JobPostingListItem",
    "JobPostingRead",
    "JobPostingUpdate",
    "MatchResultCreate",
    "MatchResultListItem",
    "MatchResultRead",
    "MatchResultUpdate",
    "ResumeCreate",
    "ResumeListItem",
    "ResumeRead",
    "ResumeUpdate",
]
