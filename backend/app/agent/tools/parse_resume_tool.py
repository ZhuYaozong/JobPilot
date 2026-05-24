"""触发简历 LLM 结构化解析,把 parse_status 从 pending → parsed。

典型链路:用户用 create_resume 落库后简历是 pending,此时 analyze_match /
generate_cover_letter 会失败("Resume needs parsing first")。Agent 调 parse_resume
让简历进入 parsed,后续动作工具就可以继续。
"""

from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.agent.tool_adapter import BaseTool, ToolContext, ToolSystemError
from app.llm.client import LLMClient
from app.services.resume_parsing_service import parse_resume
from app.services.user_scope_service import get_resume_for_user_or_404


_BUSINESS_DETAIL_TO_ERROR_CLASS: dict[str, str] = {
    "Resume not found": "resume_not_found",
    "Resume raw text is empty": "resume_raw_text_empty",
}

_BUSINESS_LLM_MESSAGES: dict[str, str] = {
    "resume_not_found": "请求的简历不存在;请让用户确认 resume_id。",
    "resume_raw_text_empty": "简历正文为空,无法解析;请让用户先补充简历内容。",
}


class ParseResumeToolArgs(BaseModel):
    resume_id: int = Field(..., description="要解析的简历 id。")


class ParseResumeTool(BaseTool):
    name = "parse_resume"
    description = (
        "对一份已落库但未解析的简历触发 LLM 结构化解析,把 parse_status 升级为 parsed。"
        "典型场景:create_resume 没带 parsed_json 时简历是 pending,后续 analyze_match / "
        "generate_cover_letter / generate_tailored_resume 会因『Resume needs parsing first』"
        "失败。先调用本工具让简历进入 parsed 状态。已经 parsed 的简历不需要再调。"
    )
    args_schema = ParseResumeToolArgs

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm_client = llm_client

    async def _execute(
        self,
        args: ParseResumeToolArgs,
        ctx: ToolContext,
    ) -> dict[str, Any]:
        try:
            resume = await get_resume_for_user_or_404(
                ctx.db,
                args.resume_id,
                ctx.current_user,
            )
        except HTTPException as exc:
            return self._http_exception_to_result(exc)

        try:
            resume = await parse_resume(ctx.db, resume, llm_client=self._llm_client)
        except HTTPException as exc:
            return self._http_exception_to_result(exc)

        return {
            "ok": True,
            "data": {
                "resume_id": resume.id,
                "parse_status": resume.parse_status,
                "parsed_json": resume.parsed_json,
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
            # LLM 配置缺失 → 500 → llm_config_missing;调用失败 / 坏 JSON → 502 → llm_unavailable
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
