"""按 id 读取岗位完整结构(含 parsed_json + jd_text)。

read_job_posting 与 ``list_user_jobs`` 互补:list 拿 id,read 拿细节(parsed_json + 原文)。

JobPosting 模型没有 parse_status 列;按 ``parsed_json is not None`` 派生,与
list_user_jobs_tool 保持一致。
"""

from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.agent.tool_adapter import BaseTool, ToolContext
from app.services.user_scope_service import get_job_posting_for_user_or_404


_BUSINESS_DETAIL_TO_ERROR_CLASS: dict[str, str] = {
    "Job posting not found": "job_posting_not_found",
}

_BUSINESS_LLM_MESSAGES: dict[str, str] = {
    "job_posting_not_found": (
        "请求的岗位不存在;请让用户确认 job_posting_id,或先调用 list_user_jobs 查找。"
    ),
}


class ReadJobPostingToolArgs(BaseModel):
    job_posting_id: int = Field(..., description="要读取的岗位 id。")


class ReadJobPostingTool(BaseTool):
    name = "read_job_posting"
    description = (
        "按 id 读取一份完整的岗位记录,包括 company_name、job_title、city、status、"
        "source_url、jd_text、parsed_json、created_at、updated_at。"
        "当 Agent 需要基于具体岗位的 JD 要求、责任、关键词等细节回答用户,或为后续动作"
        "工具提供事实依据时使用。优先级:list_user_jobs 找 id → read_job_posting 拉细节。"
        "已经在对话历史 / 摘要 / 之前工具结果里看到过完整字段时,不要重复调用。"
    )
    args_schema = ReadJobPostingToolArgs

    async def _execute(
        self,
        args: ReadJobPostingToolArgs,
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

        return {
            "ok": True,
            "data": {
                "id": job.id,
                "company_name": job.company_name,
                "job_title": job.job_title,
                "city": job.city,
                "status": job.status,
                "source_url": job.source_url,
                "jd_text": job.jd_text,
                "parsed_json": job.parsed_json,
                # JobPosting 没有独立的 parse_status 列;派生方式与 list_user_jobs 一致。
                "parse_status": "parsed" if job.parsed_json else "pending",
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "updated_at": job.updated_at.isoformat() if job.updated_at else None,
            },
        }

    def _http_exception_to_result(self, exc: HTTPException) -> dict[str, Any]:
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        error_class = _BUSINESS_DETAIL_TO_ERROR_CLASS.get(detail, "unknown_business_error")
        return {
            "ok": False,
            "error_class": error_class,
            "message_for_llm": _BUSINESS_LLM_MESSAGES.get(error_class, detail),
            "user_facing_detail": detail,
        }
