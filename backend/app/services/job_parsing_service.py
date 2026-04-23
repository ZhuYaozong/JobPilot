import json
from json import JSONDecodeError

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.client import LLMClient, LLMClientError, LLMConfigError
from app.models.job_posting import JobPosting
from app.schemas.job_parsing import JobParsingResult


def build_job_parsing_prompt(job: JobPosting) -> str:
    return f"""You are a job description parser.
Extract structured information from the following job description.
Return JSON only, with this shape:
{{
  "summary": string or null,
  "responsibilities": string[],
  "required_skills": string[],
  "preferred_skills": string[],
  "keywords": string[],
  "seniority": string or null,
  "city": string or null
}}

Job title: {job.job_title}
Company: {job.company_name}
City: {job.city or ""}
Job description:
{job.jd_text}
"""


async def parse_job_posting(
    db: AsyncSession,
    job: JobPosting,
    llm_client: LLMClient | None = None,
) -> JobPosting:
    if not job.jd_text or not job.jd_text.strip():
        raise HTTPException(status_code=400, detail="Job description is empty")

    client = llm_client or LLMClient()
    prompt = build_job_parsing_prompt(job)

    try:
        raw_result = await client.generate_text(prompt)
    except LLMConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except LLMClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    try:
        parsed_data = json.loads(raw_result)
        result = JobParsingResult.model_validate(parsed_data)
    except JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="LLM response is not valid JSON") from exc
    except ValidationError as exc:
        raise HTTPException(
            status_code=502,
            detail="LLM response does not match job parsing schema",
        ) from exc

    job.parsed_json = result.model_dump()
    await db.commit()
    await db.refresh(job)
    return job
