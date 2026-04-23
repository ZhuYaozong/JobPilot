import json
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.client import LLMClient, LLMClientError, LLMConfigError
from app.models.application_record import ApplicationRecord
from app.models.generated_artifact import GeneratedArtifact
from app.models.job_posting import JobPosting
from app.models.match_result import MatchResult
from app.models.resume import Resume
from app.schemas.cover_letter_generation import (
    CoverLetterGenerateRequest,
    CoverLetterGenerationMeta,
)

SUPPORTED_LANGUAGE_MODES = {"zh", "bilingual"}


def contains_chinese_text(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def build_key_points(match: MatchResult) -> list[str]:
    values: list[Any] = []
    for field in (match.strengths, match.suggestions):
        if field:
            values.extend(field)

    return [str(value) for value in values if str(value).strip()][:5]


def build_cover_letter_prompt(
    resume: Resume,
    job: JobPosting,
    match: MatchResult,
    language_mode: str,
) -> str:
    resume_json = json.dumps(resume.parsed_json, ensure_ascii=False, indent=2)
    job_json = json.dumps(job.parsed_json, ensure_ascii=False, indent=2)
    match_json = json.dumps(
        {
            "overall_score": match.overall_score,
            "strengths": match.strengths or [],
            "weaknesses": match.weaknesses or [],
            "missing_keywords": match.missing_keywords or [],
            "suggestions": match.suggestions or [],
        },
        ensure_ascii=False,
        indent=2,
    )

    language_instruction = (
        "Write only a Chinese cover letter draft."
        if language_mode == "zh"
        else "Write the Chinese version first, then the English version."
    )

    return f"""You are a job application writing assistant.
Generate a concise, role-specific cover letter draft based on the structured resume,
structured job description, and match analysis.
{language_instruction}
Do not write unrelated boilerplate. Keep it short enough to edit as a draft.
Return plain text only.

Resume structured JSON:
{resume_json}

Job posting structured JSON:
{job_json}

Latest match result:
{match_json}
"""


def validate_generated_cover_letter(content_text: str, language_mode: str) -> str:
    text = content_text.strip()
    if not text:
        raise HTTPException(status_code=502, detail="Generated cover letter is empty")

    if language_mode in {"zh", "bilingual"} and not contains_chinese_text(text):
        raise HTTPException(
            status_code=502,
            detail="Generated cover letter must contain Chinese content",
        )

    return text


async def get_latest_match_result(
    db: AsyncSession,
    resume_id: int,
    job_posting_id: int,
) -> MatchResult | None:
    statement = (
        select(MatchResult)
        .where(
            MatchResult.resume_id == resume_id,
            MatchResult.job_posting_id == job_posting_id,
        )
        .order_by(MatchResult.created_at.desc(), MatchResult.id.desc())
        .limit(1)
    )
    result = await db.execute(statement)
    return result.scalar_one_or_none()


async def generate_cover_letter(
    db: AsyncSession,
    payload: CoverLetterGenerateRequest,
    llm_client: LLMClient | None = None,
) -> GeneratedArtifact:
    if payload.language_mode not in SUPPORTED_LANGUAGE_MODES:
        raise HTTPException(status_code=400, detail="Unsupported language_mode")

    resume = await db.get(Resume, payload.resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")

    job = await db.get(JobPosting, payload.job_posting_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job posting not found")

    application: ApplicationRecord | None = None
    if payload.application_record_id is not None:
        application = await db.get(ApplicationRecord, payload.application_record_id)
        if application is None:
            raise HTTPException(status_code=404, detail="Application record not found")
        if (
            application.resume_id != payload.resume_id
            or application.job_posting_id != payload.job_posting_id
        ):
            raise HTTPException(
                status_code=400,
                detail="Application record does not match resume and job posting",
            )

    if not resume.parsed_json:
        raise HTTPException(status_code=400, detail="Resume needs parsing first")

    if not job.parsed_json:
        raise HTTPException(status_code=400, detail="Job posting needs parsing first")

    match = await get_latest_match_result(db, payload.resume_id, payload.job_posting_id)
    if match is None:
        raise HTTPException(status_code=400, detail="Match analysis is required first")

    client = llm_client or LLMClient()
    prompt = build_cover_letter_prompt(resume, job, match, payload.language_mode)

    try:
        raw_content = await client.generate_text(prompt)
    except LLMConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except LLMClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    content_text = validate_generated_cover_letter(raw_content, payload.language_mode)
    meta = CoverLetterGenerationMeta(
        language_mode=payload.language_mode,
        key_points=build_key_points(match),
        based_on_match_result_id=match.id,
    )

    artifact = GeneratedArtifact(
        artifact_type="cover_letter",
        resume_id=resume.id,
        job_posting_id=job.id,
        application_record_id=application.id if application else None,
        title=f"Cover Letter Draft - {job.job_title}",
        content_text=content_text,
        content_json=meta.model_dump(),
        status="draft",
        generator_type="ai",
    )
    db.add(artifact)
    await db.commit()
    await db.refresh(artifact)
    return artifact
