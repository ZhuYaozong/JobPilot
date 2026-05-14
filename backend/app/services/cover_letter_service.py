import json
from typing import Any

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.client import LLMClient, LLMClientError, LLMConfigError
from app.models.application_record import ApplicationRecord
from app.models.generated_artifact import GeneratedArtifact
from app.models.job_posting import JobPosting
from app.models.match_result import MatchResult
from app.models.resume import Resume
from app.models.user import User
from app.schemas.cover_letter_generation import (
    CoverLetterGenerateRequest,
    CoverLetterGenerationMeta,
)
from app.services.user_scope_service import (
    get_application_record_for_user_or_404,
    get_job_posting_for_user_or_404,
    get_latest_match_result_for_user,
    get_resume_for_user_or_404,
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
        "只写中文求职信草稿。"
        if language_mode == "zh"
        else "先写中文版本，再写英文版本。"
    )

    return f"""你是 JobPilot 的求职信写作助手。
请基于结构化简历、结构化岗位描述和最新匹配分析，生成一份贴合岗位的求职信草稿。
{language_instruction}
输出风格:
- 只返回纯文本，不要返回 JSON、Markdown 标题或解释说明。
- 内容要具体关联岗位与候选人经历，不要写空泛套话。
- 保持简洁，适合作为用户后续编辑的草稿。
- 不要编造简历中不存在的经历、项目、指标、奖项、时间或技能。

简历结构化 JSON:
{resume_json}

岗位结构化 JSON:
{job_json}

最新匹配结果:
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


async def generate_cover_letter(
    db: AsyncSession,
    payload: CoverLetterGenerateRequest,
    current_user: User,
    llm_client: LLMClient | None = None,
) -> GeneratedArtifact:
    if payload.language_mode not in SUPPORTED_LANGUAGE_MODES:
        raise HTTPException(status_code=400, detail="Unsupported language_mode")

    resume = await get_resume_for_user_or_404(db, payload.resume_id, current_user)
    job = await get_job_posting_for_user_or_404(
        db,
        payload.job_posting_id,
        current_user,
    )

    application: ApplicationRecord | None = None
    if payload.application_record_id is not None:
        application = await get_application_record_for_user_or_404(
            db,
            payload.application_record_id,
            current_user,
        )
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

    match = await get_latest_match_result_for_user(
        db,
        current_user,
        payload.resume_id,
        payload.job_posting_id,
    )
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
        user_id=current_user.id,
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
