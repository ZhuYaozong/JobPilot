import json
from json import JSONDecodeError

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.client import LLMClient, LLMClientError, LLMConfigError
from app.llm.json_utils import load_llm_json
from app.models.application_record import ApplicationRecord
from app.models.job_posting import JobPosting
from app.models.match_result import MatchResult
from app.models.resume import Resume
from app.models.resume_version import ResumeVersion
from app.models.user import User
from app.schemas.tailored_resume_generation import (
    TailoredResumeGenerateRequest,
    TailoredResumeLLMOutput,
)
from app.services.user_scope_service import (
    get_application_record_for_user_or_404,
    get_job_posting_for_user_or_404,
    get_latest_match_result_for_user,
    get_resume_for_user_or_404,
)


def build_tailored_resume_prompt(
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

    return f"""你是 JobPilot 的真实简历定制助手。
请基于原始简历、结构化岗位描述和最新匹配分析，生成一份针对该岗位的 Markdown 简历变体。

只返回 JSON，不要返回解释、Markdown 代码块或额外前后缀。JSON 字段名必须严格保持以下英文名称和结构:
{{
  "version_label": "中文短标签,不超过 255 个字符",
  "content_markdown": "Markdown 格式的定制简历正文",
  "change_summary": ["中文变更摘要条目", "..."]
}}

硬性约束:
- 不得编造不存在的经历、项目、指标、奖项、时间、技能、公司、职级或学历。
- 不要加入任何原始简历或结构化简历 JSON 不支持的事实。
- 可以调整章节顺序、改写表达、突出相关事实、删减不相关内容。
- 如果岗位要求某项技能但简历没有证据，不要把它写成候选人已掌握的技能；必要时只在 change_summary 中说明该差距。
- content_markdown 要实用、可编辑，不要在 JSON 外输出任何解释。

原始简历正文:
{resume.raw_text}

简历结构化 JSON:
{resume_json}

岗位结构化 JSON:
{job_json}

最新匹配结果:
{match_json}
"""


def validate_tailored_resume_output(raw_content: str) -> TailoredResumeLLMOutput:
    try:
        parsed_data = load_llm_json(raw_content)
        output = TailoredResumeLLMOutput.model_validate(parsed_data)
    except JSONDecodeError as exc:
        raise HTTPException(
            status_code=502,
            detail="LLM response is not valid JSON",
        ) from exc
    except ValidationError as exc:
        raise HTTPException(
            status_code=502,
            detail="LLM response does not match tailored resume schema",
        ) from exc

    label = output.version_label.strip()
    content = output.content_markdown.strip()
    summaries = [
        item.strip()
        for item in output.change_summary
        if isinstance(item, str) and item.strip()
    ][:12]

    if not content:
        raise HTTPException(status_code=502, detail="Generated tailored resume is empty")
    if not label:
        raise HTTPException(
            status_code=502,
            detail="Generated tailored resume label is empty",
        )

    return TailoredResumeLLMOutput(
        version_label=label[:255],
        content_markdown=content,
        change_summary=summaries,
    )


async def generate_tailored_resume_version(
    db: AsyncSession,
    payload: TailoredResumeGenerateRequest,
    current_user: User,
    llm_client: LLMClient | None = None,
) -> ResumeVersion:
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
    prompt = build_tailored_resume_prompt(resume, job, match)
    try:
        raw_content = await client.generate_text(prompt)
    except LLMConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except LLMClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    output = validate_tailored_resume_output(raw_content)
    version_no = await _next_version_no(db, payload.resume_id)
    version = ResumeVersion(
        resume_id=resume.id,
        job_posting_id=job.id,
        version_no=version_no,
        version_label=output.version_label,
        content=output.content_markdown,
        content_format="markdown",
        source_type="ai_tailored",
        change_summary=_format_change_summary(output.change_summary),
        is_active=True,
    )
    db.add(version)
    await db.commit()
    await db.refresh(version)
    return version


async def _next_version_no(db: AsyncSession, resume_id: int) -> int:
    result = await db.execute(
        select(func.coalesce(func.max(ResumeVersion.version_no), 0)).where(
            ResumeVersion.resume_id == resume_id,
        ),
    )
    return int(result.scalar_one()) + 1


def _format_change_summary(items: list[str]) -> str | None:
    if not items:
        return None
    return "\n".join(f"- {item}" for item in items)
