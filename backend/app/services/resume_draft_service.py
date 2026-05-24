"""草稿模式简历:基于用户文本,让 LLM 推断 title + 结构化抽取。

跟 ``resume_parsing_service`` 的区别:
- parsing 是对已落库简历进行结构化,前提是已经有 raw_text 和 title。
- draft 是用户给一段任意文本,需要 LLM 同时建议 title + 结构。结果不入库,
  返回 ``ResumeDraftResponse``,前端走"预览 → 编辑 → 保存"。
"""

from __future__ import annotations

from json import JSONDecodeError

from fastapi import HTTPException
from pydantic import BaseModel, Field, ValidationError

from app.llm.client import LLMClient, LLMClientError, LLMConfigError
from app.llm.json_utils import load_llm_json
from app.schemas.resume_draft import ResumeDraftResponse
from app.schemas.resume_parsing import ResumeParsingResult


class _ResumeDraftLLMOutput(BaseModel):
    """LLM 直接返回的 JSON 形状,内部用,不暴露给 API。"""

    title: str = Field(..., min_length=1, max_length=255)
    parsed: ResumeParsingResult


def build_resume_draft_prompt(text: str) -> str:
    return f"""你是 JobPilot 的简历草稿助手。
用户粘贴了一段简历文本,请同时:
1) 推断一个简洁的中文简历标题(候选人姓名 + 目标方向,或者只有姓名;不要带标点字母);
2) 抽取结构化字段。

只返回 JSON,不要返回解释、Markdown 或代码块。JSON 字段名必须严格保持以下英文名称和结构:
{{
  "title": "中文简历标题,不超过 60 个字符",
  "parsed": {{
    "summary": string or null,
    "skills": string[],
    "experiences": string[],
    "projects": string[],
    "education": string[],
    "target_roles": string[],
    "years_of_experience": string or null
  }}
}}

业务规则:
- 只根据原文抽取,不要补写不存在的经历、技能、学历或年限。
- summary 用一两句话概括候选人核心定位;原文不足时返回 null。
- experiences / projects / education 保持简洁,可用中文短句概括。
- target_roles 只能从简历明确表达的目标岗位或经历方向中推断;不确定返回空数组。
- years_of_experience 无法判断时返回 null。
- title 不要带"简历""resume"这种通用词;尽量像"张三 后端开发简历"或"李四 简历"。

简历原文:
{text}
"""


async def generate_resume_draft(
    text: str,
    *,
    llm_client: LLMClient | None = None,
) -> ResumeDraftResponse:
    """运行简历草稿生成。

    text 为空在 schema 层已经拦截;这里只关心 LLM 与解析失败。
    """
    cleaned = text.strip()
    if not cleaned:
        # 双保险,虽然 schema 的 min_length=1 已经卡住空字符串
        raise HTTPException(status_code=400, detail="Resume text is empty")

    client = llm_client or LLMClient()
    prompt = build_resume_draft_prompt(cleaned)

    try:
        raw_result = await client.generate_text(prompt)
    except LLMConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except LLMClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    try:
        parsed_payload = load_llm_json(raw_result)
        output = _ResumeDraftLLMOutput.model_validate(parsed_payload)
    except JSONDecodeError as exc:
        raise HTTPException(
            status_code=502, detail="LLM response is not valid JSON",
        ) from exc
    except ValidationError as exc:
        raise HTTPException(
            status_code=502,
            detail="LLM response does not match resume draft schema",
        ) from exc

    return ResumeDraftResponse(
        title=output.title.strip()[:255],
        raw_text=cleaned,
        parsed_json=output.parsed,
    )
