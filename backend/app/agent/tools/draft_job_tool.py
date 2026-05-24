"""把 job_draft_service.generate_job_draft 包装成 Agent 工具。

draft_job 属于"组合工具":调用 LLM、不写数据库,只返回一份岗位草稿。
ReAct 设计上,Agent 应该先调 draft_job 把草稿展示给用户,等用户确认或要求修改后,
再调用 create_job 真正落库。

错误契约沿用同目录其它动作工具:已知业务错(URL 抓取失败 / 空输入)走
``ok=false``,LLM 层异常抛 ``ToolSystemError``。
"""

from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.agent.tool_adapter import BaseTool, ToolContext, ToolSystemError
from app.llm.client import LLMClient
from app.schemas.job_draft import JobDraftRequest
from app.services.job_draft_service import generate_job_draft


# 已知业务错误明细 → 稳定 error_class,这两个都是用户/输入可补的问题。
_BUSINESS_DETAIL_TO_ERROR_CLASS: dict[str, str] = {
    "JD text is empty": "draft_input_empty",
}

# 提示文案给 LLM 看,帮它把内部错误转成下一步建议(不要暴露 error_class)。
_BUSINESS_LLM_MESSAGES: dict[str, str] = {
    "draft_input_empty": "JD 文本和 URL 都为空;请让用户至少提供其中一项。",
    "url_fetch_failed": "无法从 URL 抓取岗位正文;请让用户改贴 JD 文本。",
}


class DraftJobToolArgs(BaseModel):
    """draft_job 工具的入参,沿用 JobDraftRequest 的 text/url 二选一规则。"""

    text: str | None = Field(
        default=None,
        description="JD 原文(粘贴模式);text 与 url 至少要提供一个。",
    )
    url: str | None = Field(
        default=None,
        description="JD 网页链接(URL 模式);text 与 url 至少要提供一个。",
    )


class DraftJobTool(BaseTool):
    name = "draft_job"
    description = (
        "把用户给的 JD 文本或岗位 URL 解析成岗位草稿:LLM 同时推断公司名、岗位名、城市,"
        "并抽取结构化 JD 字段。不会写入数据库,返回的字段可直接喂给 create_job 落库。"
        "用户说『帮我加一个岗位』『把这段 JD 录入』『把这个链接里的岗位存下来』时使用本工具。"
        "得到草稿后请先用 respond_directly 把摘要给用户看,等用户确认或修改后再调 create_job。"
    )
    args_schema = DraftJobToolArgs

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm_client = llm_client

    async def _execute(
        self,
        args: DraftJobToolArgs,
        ctx: ToolContext,  # noqa: ARG002 — draft 不落库,不需要 db/current_user
    ) -> dict[str, Any]:
        # JobDraftRequest 的 model_validator 会再次校验 text/url 至少一项非空,
        # 工具层把这一类映射成业务错,让模型继续追问用户。
        try:
            payload = JobDraftRequest(text=args.text, url=args.url)
        except ValueError as exc:
            # Pydantic v2 把 model_validator 的 ValueError 包成 ValidationError;
            # 这里出现 ValueError 说明是简单参数错,转业务错即可。
            return {
                "ok": False,
                "error_class": "draft_input_empty",
                "message_for_llm": _BUSINESS_LLM_MESSAGES["draft_input_empty"],
                "user_facing_detail": str(exc),
            }

        try:
            draft = await generate_job_draft(payload, llm_client=self._llm_client)
        except HTTPException as exc:
            return self._http_exception_to_result(exc)

        return {
            "ok": True,
            "data": {
                "company_name": draft.company_name,
                "job_title": draft.job_title,
                "city": draft.city,
                "jd_text": draft.jd_text,
                "source_url": draft.source_url,
                # parsed_json 是 JobParsingResult,用 model_dump 转成纯 dict 方便后续 create_job 复用。
                "parsed_json": draft.parsed_json.model_dump(),
            },
        }

    def _http_exception_to_result(self, exc: HTTPException) -> dict[str, Any]:
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)

        # URL 抓取失败时 service 用 422 + 用户友好文案,直接走业务错让模型转述。
        if exc.status_code == 422:
            return {
                "ok": False,
                "error_class": "url_fetch_failed",
                "message_for_llm": _BUSINESS_LLM_MESSAGES["url_fetch_failed"],
                "user_facing_detail": detail,
            }

        # 其它已知映射(例如 "JD text is empty",service 仍可能返回 400)。
        error_class = _BUSINESS_DETAIL_TO_ERROR_CLASS.get(detail)
        if error_class is not None:
            return {
                "ok": False,
                "error_class": error_class,
                "message_for_llm": _BUSINESS_LLM_MESSAGES.get(error_class, detail),
                "user_facing_detail": detail,
            }

        if exc.status_code >= 500:
            # LLM 配置缺失走 500、LLM 调用失败走 502,统一转成 ToolSystemError。
            raise ToolSystemError(
                self.name,
                error_class="llm_unavailable" if exc.status_code == 502 else "llm_config_missing",
                detail=detail,
            )

        return {
            "ok": False,
            "error_class": "unknown_business_error",
            "message_for_llm": detail,
            "user_facing_detail": detail,
        }
