from pydantic import BaseModel, Field


class TailoredResumeGenerateRequest(BaseModel):
    resume_id: int
    job_posting_id: int
    application_record_id: int | None = None


class TailoredResumeLLMOutput(BaseModel):
    version_label: str = Field(min_length=1, max_length=255)
    content_markdown: str = Field(min_length=1)
    change_summary: list[str] = Field(default_factory=list)

