"""触发岗位 LLM 结构化解析,把 parsed_json 从 NULL 填上。

典型链路:用户用 create_job 落库后岗位是 pending(没 parsed_json),后续动作工具
("Job posting needs parsing first")会拒绝。Agent 调 parse_job_posting 让岗位进入
parsed 状态。
"""

from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.agent.tool_adapter import BaseTool, ToolContext, ToolSystemError
from app.llm.client import LLMClient
from app.services.job_parsing_service import parse_job_posting
from app.services.user_scope_service import get_job_posting_for_user_or_404


_BUSINESS_DETAIL_TO_ERROR_CLASS: dict[str, str] = {
    "Job posting not found": "job_posting_not_found",
    "Job description is empty": "job_jd_text_empty",
}

_BUSINESS_LLM_MESSAGES: dict[str, str] = {
    "job_posting_not_found": "请求的岗位不存在;请让用户确认 job_posting_id。",
    "job_jd_text_empty": "岗位 JD 为空,无法解析;请让用户补充 JD 内容后重试。",
}


class ParseJobPostingToolArgs(BaseModel):
    job_posting_id: int = Field(..., description="要解析的岗位 id。")


class ParseJobPostingTool(BaseTool):
    name = "parse_job_posting"
    description = (
        "对一份已落库但未解析的岗位触发 LLM 结构化抽取,填充 parsed_json。"
        "典型场景:create_job 没带 parsed_json 时岗位的 parsed_json 为 NULL,后续 "
        "analyze_match / generate_cover_letter / generate_interview_prep / "
        "generate_tailored_resume 会因『Job posting needs parsing first』失败。"
        "先调用本工具让岗位进入 parsed 状态。已经 parsed 的岗位不需要再调。"
    )
    args_schema = ParseJobPostingToolArgs

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm_client = llm_client

    async def _execute(
        self,
        args: ParseJobPostingToolArgs,
        ctx: ToolContext,
    ) -> dict[str, Any]:
        try:
            job = await get_job_posting_for_user_or_404(
                ctx.db,
                args.job_posting_id,
                ctx.current_user,
            )
        except HTTPException as exc:
            return self._http_exception_to_result(exc)

        try:
            job = await parse_job_posting(ctx.db, job, llm_client=self._llm_client)
        except HTTPException as exc:
            return self._http_exception_to_result(exc)

        return {
            "ok": True,
            "data": {
                "job_posting_id": job.id,
                # 与 list_user_jobs / read_job_posting 一致,parse_status 派生。
                "parse_status": "parsed" if job.parsed_json else "pending",
                "parsed_json": job.parsed_json,
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
