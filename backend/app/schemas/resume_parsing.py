from pydantic import BaseModel, Field


class ResumeParsingResult(BaseModel):
    summary: str | None = None
    skills: list[str] = Field(default_factory=list)
    experiences: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    target_roles: list[str] = Field(default_factory=list)
    years_of_experience: str | None = None
