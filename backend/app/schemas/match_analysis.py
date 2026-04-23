from pydantic import BaseModel, Field


class MatchAnalysisRequest(BaseModel):
    resume_id: int
    job_posting_id: int


class MatchAnalysisResult(BaseModel):
    overall_score: float = Field(ge=0, le=100)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    missing_keywords: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
