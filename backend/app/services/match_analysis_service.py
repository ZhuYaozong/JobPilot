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
from app.models.user import User
from app.schemas.match_analysis import MatchAnalysisRequest, MatchAnalysisResult
from app.services.user_scope_service import ensure_resume_and_job_exist_for_user


def build_match_analysis_prompt(resume: Resume, job: JobPosting) -> str:
    resume_json = json.dumps(resume.parsed_json, ensure_ascii=False, indent=2)
    job_json = json.dumps(job.parsed_json, ensure_ascii=False, indent=2)

    return f"""你是 JobPilot 的岗位匹配分析师。
请比较结构化简历和结构化岗位描述，评估候选人与岗位的匹配度。
只返回 JSON，不要返回解释、Markdown 或代码块。JSON 字段名必须严格保持以下英文名称和结构:
{{
  "overall_score": 0 到 100 的数字,
  "strengths": string[],
  "weaknesses": string[],
  "missing_keywords": string[],
  "suggestions": string[]
}}

行为约束:
- 所有判断必须基于输入的结构化 JSON，不要编造简历或岗位中没有的事实。
- strengths 写候选人已经具备、且和岗位相关的优势。
- weaknesses 写与岗位要求相比的短板或风险。
- missing_keywords 写岗位要求中明显缺失或弱覆盖的关键词。
- suggestions 写可执行的简历修改或准备建议。
- 列表项保持简洁，优先使用中文表达。

简历结构化 JSON:
{resume_json}

岗位结构化 JSON:
{job_json}
"""


async def analyze_match(
    db: AsyncSession,
    payload: MatchAnalysisRequest,
    current_user: User,
    llm_client: LLMClient | None = None,
) -> MatchResult:
    resume, job = await ensure_resume_and_job_exist_for_user(
        db,
        payload.resume_id,
        payload.job_posting_id,
        current_user,
    )

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
        user_id=current_user.id,
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
