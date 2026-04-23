from pydantic import BaseModel, Field


class CoverLetterGenerateRequest(BaseModel):
    resume_id: int
    job_posting_id: int
    application_record_id: int | None = None
    language_mode: str = "zh"


class CoverLetterGenerationMeta(BaseModel):
    artifact_type: str = "cover_letter"
    language_mode: str
    key_points: list[str] = Field(default_factory=list)
    based_on_match_result_id: int | None = None
