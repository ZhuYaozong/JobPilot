from json import JSONDecodeError

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.client import LLMClient, LLMClientError, LLMConfigError
from app.llm.json_utils import load_llm_json
from app.models.resume import Resume
from app.schemas.resume_parsing import ResumeParsingResult


def build_resume_parsing_prompt(resume: Resume) -> str:
    return f"""你是 JobPilot 的简历结构化解析器。
请从下面的简历文本中抽取结构化内容。
只返回 JSON，不要返回解释、Markdown 或代码块。JSON 字段名必须严格保持以下英文名称和结构:
{{
  "summary": string or null,
  "skills": string[],
  "experiences": string[],
  "projects": string[],
  "education": string[],
  "target_roles": string[],
  "years_of_experience": string or null
}}

业务规则:
- 只根据简历原文抽取信息，不要补写不存在的经历、技能、学历或年限。
- experiences / projects / education 保持简洁，可用中文概括。
- target_roles 只能从简历明确表达的目标岗位或经历方向中推断；不确定时返回空数组。
- years_of_experience 无法从原文判断时返回 null。

简历标题: {resume.title}
简历正文:
{resume.raw_text}
"""


async def parse_resume(
    db: AsyncSession,
    resume: Resume,
    llm_client: LLMClient | None = None,
) -> Resume:
    if not resume.raw_text or not resume.raw_text.strip():
        raise HTTPException(status_code=400, detail="Resume raw text is empty")

    client = llm_client or LLMClient()
    prompt = build_resume_parsing_prompt(resume)

    try:
        raw_result = await client.generate_text(prompt)
    except LLMConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except LLMClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    try:
        parsed_data = load_llm_json(raw_result)
        result = ResumeParsingResult.model_validate(parsed_data)
    except JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="LLM response is not valid JSON") from exc
    except ValidationError as exc:
        raise HTTPException(
            status_code=502,
            detail="LLM response does not match resume parsing schema",
        ) from exc

    resume.parsed_json = result.model_dump()
    resume.parse_status = "parsed"
    await db.commit()
    await db.refresh(resume)
    return resume
