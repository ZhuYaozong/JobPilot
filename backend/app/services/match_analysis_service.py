import json
from json import JSONDecodeError

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.client import LLMClient, LLMClientError, LLMConfigError
from app.llm.json_utils import load_llm_json
from app.models.job_posting import JobPosting
from app.models.match_result import MatchResult
from app.models.resume import Resume
from app.schemas.match_analysis import MatchAnalysisRequest, MatchAnalysisResult


def build_match_analysis_prompt(resume: Resume, job: JobPosting) -> str:
    resume_json = json.dumps(resume.parsed_json, ensure_ascii=False, indent=2)
    job_json = json.dumps(job.parsed_json, ensure_ascii=False, indent=2)

    return f"""You are a job application match analyst.
Compare the structured resume with the structured job description.
Return JSON only, with this shape:
{{
  "overall_score": number from 0 to 100,
  "strengths": string[],
  "weaknesses": string[],
  "missing_keywords": string[],
  "suggestions": string[]
}}

Keep list items concise. Base the analysis on the structured JSON inputs.

Resume structured JSON:
{resume_json}

Job posting structured JSON:
{job_json}
"""


async def analyze_match(
    db: AsyncSession,
    payload: MatchAnalysisRequest,
    llm_client: LLMClient | None = None,
) -> MatchResult:
    resume = await db.get(Resume, payload.resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")

    job = await db.get(JobPosting, payload.job_posting_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job posting not found")

    if not resume.parsed_json:
        raise HTTPException(status_code=400, detail="Resume needs parsing first")

    if not job.parsed_json:
        raise HTTPException(status_code=400, detail="Job posting needs parsing first")

    client = llm_client or LLMClient()
    prompt = build_match_analysis_prompt(resume, job)

    try:
        raw_result = await client.generate_text(prompt)
    except LLMConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except LLMClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    try:
        parsed_data = load_llm_json(raw_result)
        result = MatchAnalysisResult.model_validate(parsed_data)
    except JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="LLM response is not valid JSON") from exc
    except ValidationError as exc:
        raise HTTPException(
            status_code=502,
            detail="LLM response does not match match analysis schema",
        ) from exc

    match = MatchResult(
        resume_id=resume.id,
        job_posting_id=job.id,
        overall_score=result.overall_score,
        strengths=result.strengths,
        weaknesses=result.weaknesses,
        missing_keywords=result.missing_keywords,
        suggestions=result.suggestions,
    )
    db.add(match)
    await db.commit()
    await db.refresh(match)
    return match
