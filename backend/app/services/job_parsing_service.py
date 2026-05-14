from json import JSONDecodeError

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.client import LLMClient, LLMClientError, LLMConfigError
from app.llm.json_utils import load_llm_json
from app.models.job_posting import JobPosting
from app.schemas.job_parsing import JobParsingResult


def build_job_parsing_prompt(job: JobPosting) -> str:
    return f"""你是 JobPilot 的岗位描述结构化解析器。
请从下面的岗位信息中抽取结构化内容。
只返回 JSON，不要返回解释、Markdown 或代码块。JSON 字段名必须严格保持以下英文名称和结构:
{{
  "summary": string or null,
  "responsibilities": string[],
  "required_skills": string[],
  "preferred_skills": string[],
  "keywords": string[],
  "seniority": string or null,
  "city": string or null
}}

业务规则:
- summary 用简洁中文概括岗位核心目标；如果原文不足以判断则返回 null。
- responsibilities 只提取岗位职责，不要混入任职要求。
- required_skills / preferred_skills / keywords 使用原文支持的信息，不要编造技能。
- seniority / city 无法确定时返回 null。

岗位名称: {job.job_title}
公司: {job.company_name}
城市: {job.city or ""}
岗位描述:
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
        parsed_data = load_llm_json(raw_result)
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
