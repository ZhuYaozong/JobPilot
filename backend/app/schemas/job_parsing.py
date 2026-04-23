from pydantic import BaseModel, Field


class JobParsingResult(BaseModel):
    summary: str | None = None
    responsibilities: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    seniority: str | None = None
    city: str | None = None
