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
from app.schemas.interview_prep_generation import (
    InterviewPrepGenerateRequest,
    InterviewPrepGenerationMeta,
)
from app.services.user_scope_service import (
    get_application_record_for_user_or_404,
    get_job_posting_for_user_or_404,
    get_latest_match_result_for_user,
    get_resume_for_user_or_404,
)


def contains_chinese_text(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


def build_focus_topics(match: MatchResult) -> list[str]:
    values: list[Any] = []
    for field in (match.missing_keywords, match.weaknesses, match.suggestions):
        if field:
            values.extend(field)

    return [str(value) for value in values if str(value).strip()][:8]


def count_interview_questions(content_text: str) -> int:
    return content_text.count("？") + content_text.count("?")


def build_interview_prep_prompt(
    resume: Resume,
    job: JobPosting,
    match: MatchResult,
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

    return f"""你是 JobPilot 的面试准备助手。
请基于结构化简历、结构化岗位描述和最新匹配分析，生成一份简洁的中文面试准备提纲。
可根据上下文包含以下部分:
- 岗位核心考察点
- 候选人优势对应点
- 风险/短板提醒
- 5 到 8 个可能面试问题或准备要点
- 准备建议
输出风格:
- 只返回纯文本，不要返回 JSON 或解释说明。
- 不要写空泛鸡汤，要围绕岗位要求、简历事实和匹配分析展开。
- 不要编造简历中不存在的经历、项目、指标、奖项、时间或技能。

简历结构化 JSON:
{resume_json}

岗位结构化 JSON:
{job_json}

最新匹配结果:
{match_json}
"""


def validate_generated_interview_prep(content_text: str) -> str:
    text = content_text.strip()
    if not text:
        raise HTTPException(status_code=502, detail="Generated interview prep is empty")

    if not contains_chinese_text(text):
        raise HTTPException(
            status_code=502,
            detail="Generated interview prep must contain Chinese content",
        )

    structure_markers = ("问题", "考察", "准备", "建议")
    if not any(marker in text for marker in structure_markers):
        raise HTTPException(
            status_code=502,
            detail="Generated interview prep is not specific enough",
        )

    return text


async def generate_interview_prep(
    db: AsyncSession,
    payload: InterviewPrepGenerateRequest,
    current_user: User,
    llm_client: LLMClient | None = None,
) -> GeneratedArtifact:
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
    prompt = build_interview_prep_prompt(resume, job, match)

    try:
        raw_content = await client.generate_text(prompt)
    except LLMConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except LLMClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    content_text = validate_generated_interview_prep(raw_content)
    meta = InterviewPrepGenerationMeta(
        based_on_match_result_id=match.id,
        focus_topics=build_focus_topics(match),
        question_count=count_interview_questions(content_text),
    )

    artifact = GeneratedArtifact(
        user_id=current_user.id,
        artifact_type="interview_prep",
        resume_id=resume.id,
        job_posting_id=job.id,
        application_record_id=application.id if application else None,
        title=f"Interview Prep - {job.job_title}",
        content_text=content_text,
        content_json=meta.model_dump(),
        status="draft",
        generator_type="ai",
    )
    db.add(artifact)
    await db.commit()
    await db.refresh(artifact)
    return artifact
