"""草稿模式岗位 service:把"文本 / URL"统一成结构化草稿。

链路:
1. URL 模式 → 调 ``fetch_jd_from_url`` 抓正文 + title/company hint;
   text 模式 → 直接用用户给的文本。
2. 把 jd 正文 + (可选的) title/company hint 喂给 LLM。
3. LLM 同时给出 company_name / job_title / city + 完整的 JobParsingResult。
4. 包成 ``JobDraftResponse`` 返回,不落库。

跟 ``job_parsing_service`` 的区别:parsing 是已有 JobPosting 的结构化补完,
draft 需要先把 company_name/job_title/city 这些基本字段也由 LLM 推断出来。
"""

from __future__ import annotations

import json
import logging
from json import JSONDecodeError
from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field, ValidationError, model_validator

from app.llm.client import LLMClient, LLMClientError, LLMConfigError
from app.llm.json_utils import load_llm_json
from app.schemas.job_draft import JobDraftRequest, JobDraftResponse
from app.schemas.job_parsing import JobParsingResult
from app.services.job_url_fetcher import JobURLFetchError, fetch_jd_from_url

logger = logging.getLogger(__name__)

# parsed 块里的字段分类,用于容错归一化。
_PARSED_LIST_FIELDS = (
    "responsibilities",
    "required_skills",
    "preferred_skills",
    "keywords",
)
_PARSED_SCALAR_FIELDS = ("summary", "seniority", "city")


class _JobDraftLLMOutput(BaseModel):
    """LLM 直接返回的 JSON 形状,内部用。

    草稿是"尽力而为"的,用户拿到后还会编辑,因此这里对真实模型的不规范输出
    做了容错(见 ``_tolerate_loose_shapes``):公司名/岗位名缺失时给空串让用户补,
    parsed 块被拍平到顶层时自动收拢,列表字段写成字符串时自动包成数组。
    """

    company_name: str = ""
    job_title: str = ""
    city: str | None = None
    parsed: JobParsingResult = Field(default_factory=JobParsingResult)

    @model_validator(mode="before")
    @classmethod
    def _tolerate_loose_shapes(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)

        # JD 没写公司/岗位时,模型会返回 null。这两个字段在响应里是必填 str,
        # 把 null(或缺失)归一为空串,让前端把空字段留给用户补全,而不是 502。
        for key in ("company_name", "job_title"):
            if data.get(key) is None:
                data[key] = ""

        parsed = data.get("parsed")
        # 模型可能把 parsed 块拍平到顶层,或干脆漏掉 parsed。
        if not isinstance(parsed, dict):
            parsed = _maybe_json_object(parsed)
        if not isinstance(parsed, dict):
            parsed = {
                key: data[key]
                for key in (*_PARSED_LIST_FIELDS, *_PARSED_SCALAR_FIELDS)
                if key in data
            }
        else:
            parsed = dict(parsed)

        # 列表字段容错:字符串 → 单元素数组,null/缺失 → 空数组。
        for key in _PARSED_LIST_FIELDS:
            value = parsed.get(key)
            if value is None:
                parsed[key] = []
            elif isinstance(value, str):
                parsed[key] = [value] if value.strip() else []

        data["parsed"] = parsed
        return data


def _maybe_json_object(value: Any) -> Any:
    """parsed 偶尔会被模型当成 JSON 字符串再嵌一层,尝试解开。"""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (JSONDecodeError, ValueError):
            return value
    return value


def build_job_draft_prompt(
    jd_text: str,
    *,
    title_hint: str | None = None,
    company_hint: str | None = None,
) -> str:
    """draft prompt 比 parsing 多了两项推断:公司名 + 岗位名。

    如果 URL 抓取给出了 title/company hint,作为辅助信息透传,LLM 仍可纠正。
    """
    hint_lines: list[str] = []
    if title_hint:
        hint_lines.append(f"页面标题猜测的岗位名: {title_hint}")
    if company_hint:
        hint_lines.append(f"页面标题猜测的公司名: {company_hint}")
    hint_block = "\n".join(hint_lines)
    if hint_block:
        hint_block = f"\n参考信息(仅供参考,可推翻):\n{hint_block}\n"

    return f"""你是 JobPilot 的岗位草稿助手。
用户给了一段 JD 文本,请同时:
1) 推断公司名(中文优先,常见公司用通用简称,例如"阿里""字节""腾讯");
2) 推断岗位名(简洁中文,例如"AI 应用研发工程师""前端开发");
3) 推断城市(无法判断时返回 null);
4) 抽取结构化 JD 字段。

只返回 JSON,不要返回解释、Markdown 或代码块。JSON 字段名必须严格保持以下英文名称和结构:
{{
  "company_name": "中文公司名",
  "job_title": "中文岗位名",
  "city": string or null,
  "parsed": {{
    "summary": string or null,
    "responsibilities": string[],
    "required_skills": string[],
    "preferred_skills": string[],
    "keywords": string[],
    "seniority": string or null,
    "city": string or null
  }}
}}

业务规则:
- 只根据 JD 原文抽取,不要编造责任、技能或公司业务。
- responsibilities 与 required_skills / preferred_skills 不要混淆。
- city 字段在外层和 parsed 内都给出;如果 JD 没提到城市,两处都返回 null。
- seniority 例如"应届/初级/中级/高级/资深";原文不足时返回 null。
{hint_block}
JD 原文:
{jd_text}
"""


async def generate_job_draft(
    payload: JobDraftRequest,
    *,
    llm_client: LLMClient | None = None,
) -> JobDraftResponse:
    """合成岗位草稿:URL → 抓取 → LLM,或 text → LLM。"""
    jd_text, source_url, title_hint, company_hint = await _resolve_jd_source(payload)

    client = llm_client or LLMClient()
    prompt = build_job_draft_prompt(
        jd_text,
        title_hint=title_hint,
        company_hint=company_hint,
    )

    try:
        raw_result = await client.generate_text(prompt)
    except LLMConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except LLMClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    try:
        parsed_payload = load_llm_json(raw_result)
    except JSONDecodeError as exc:
        # 打出原始响应方便排查:是被 token 截断,还是模型返回了非 JSON。
        logger.warning(
            "岗位草稿 LLM 返回非合法 JSON,原始响应(截断): %s",
            raw_result[:800],
        )
        raise HTTPException(
            status_code=502, detail="LLM response is not valid JSON",
        ) from exc

    try:
        output = _JobDraftLLMOutput.model_validate(parsed_payload)
    except ValidationError as exc:
        logger.warning(
            "岗位草稿 LLM 结构异常: %s | 解析后载荷(截断): %s",
            exc.errors(),
            str(parsed_payload)[:800],
        )
        raise HTTPException(
            status_code=502,
            detail="LLM response does not match job draft schema",
        ) from exc

    return JobDraftResponse(
        company_name=output.company_name.strip()[:255],
        job_title=output.job_title.strip()[:255],
        city=(output.city or "").strip()[:100] or None,
        jd_text=jd_text,
        source_url=source_url,
        parsed_json=output.parsed,
    )


async def _resolve_jd_source(
    payload: JobDraftRequest,
) -> tuple[str, str | None, str | None, str | None]:
    """根据 text / url 解析出 (jd_text, source_url, title_hint, company_hint)。

    URL 抓取失败时把 JobURLFetchError 映射成 422,文案直接展示给用户。
    """
    if payload.url and payload.url.strip():
        try:
            fetched = await fetch_jd_from_url(payload.url.strip())
        except JobURLFetchError as exc:
            raise HTTPException(status_code=422, detail=exc.user_message) from exc
        return (
            fetched.jd_text,
            fetched.source_url,
            fetched.title,
            fetched.company_hint,
        )

    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="JD text is empty")
    return text, None, None, None
