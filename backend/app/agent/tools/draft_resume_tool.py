"""把 resume_draft_service.generate_resume_draft 包装成 Agent 工具。

draft_resume 跟 draft_job 是同一类"组合工具":调用 LLM、不写数据库,只返回一份简历草稿。
典型 ReAct 链路:用户贴简历文本 → draft_resume → respond_directly 展示草稿 →
用户确认后 → create_resume 落库。
"""

from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.agent.tool_adapter import BaseTool, ToolContext, ToolSystemError
from app.llm.client import LLMClient
from app.services.resume_draft_service import generate_resume_draft


_BUSINESS_DETAIL_TO_ERROR_CLASS: dict[str, str] = {
    "Resume text is empty": "missing_required_field",
}

# write 类工具的"必填字段缺失"业务错统一引导 LLM 用 respond_directly 向用户追问,
# 不要瞎填字段重试。
_BUSINESS_LLM_MESSAGES: dict[str, str] = {
    "missing_required_field": (
        "缺少简历正文。请用 respond_directly 向用户追问:把要起草的简历文本发过来。"
        "**不要**自己瞎填 text 重试。"
    ),
}


class DraftResumeToolArgs(BaseModel):
    """draft_resume 的入参,text 为简历正文。

    text 字段对外是 optional,允许 LLM 在还没拿到用户输入时也能合法调用,
    走 missing_required_field 业务错让 LLM 转去用 respond_directly 询问用户。
    """

    text: str | None = Field(
        default=None,
        description=(
            "用户粘贴的简历正文,LLM 会推断标题并抽取结构化字段。"
            "为空时本工具返回 missing_required_field 业务错,Agent 应当用 respond_directly 询问用户。"
        ),
    )


class DraftResumeTool(BaseTool):
    name = "draft_resume"
    description = (
        "把用户给的简历文本解析成简历草稿:LLM 推断中文标题并抽取结构化字段。"
        "不会写入数据库,返回的字段可直接喂给 create_resume 落库。"
        "用户说『帮我加一份简历』『把这段简历录入』时使用本工具。"
        "得到草稿后请先用 respond_directly 把摘要给用户看,等用户确认或修改后再调 create_resume。"
    )
    args_schema = DraftResumeToolArgs

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm_client = llm_client

    async def _execute(
        self,
        args: DraftResumeToolArgs,
        ctx: ToolContext,  # noqa: ARG002 — draft 不落库,不需要 db/current_user
    ) -> dict[str, Any]:
        # 缺简历正文 → 业务错让 LLM 转去 respond_directly 询问;不抛 ValidationError。
        if not args.text or not args.text.strip():
            return {
                "ok": False,
                "error_class": "missing_required_field",
                "message_for_llm": _BUSINESS_LLM_MESSAGES["missing_required_field"],
                "user_facing_detail": "缺少必填字段: text(简历正文)",
                "missing_fields": ["text"],
            }

        try:
            draft = await generate_resume_draft(args.text, llm_client=self._llm_client)
        except HTTPException as exc:
            return self._http_exception_to_result(exc)

        return {
            "ok": True,
            "data": {
                "title": draft.title,
                "raw_text": draft.raw_text,
                # parsed_json 是 ResumeParsingResult,转成纯 dict 供 create_resume 复用。
                "parsed_json": draft.parsed_json.model_dump(),
            },
        }

    def _http_exception_to_result(self, exc: HTTPException) -> dict[str, Any]:
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        error_class = _BUSINESS_DETAIL_TO_ERROR_CLASS.get(detail)

        if error_class is not None:
            return {
                "ok": False,
                "error_class": error_class,
                "message_for_llm": _BUSINESS_LLM_MESSAGES.get(error_class, detail),
                "user_facing_detail": detail,
            }

        if exc.status_code >= 500:
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
