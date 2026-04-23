from pydantic import BaseModel, Field


class InterviewPrepGenerateRequest(BaseModel):
    resume_id: int
    job_posting_id: int
    application_record_id: int | None = None


class InterviewPrepGenerationMeta(BaseModel):
    artifact_type: str = "interview_prep"
    based_on_match_result_id: int | None = None
    focus_topics: list[str] = Field(default_factory=list)
    question_count: int = 0
