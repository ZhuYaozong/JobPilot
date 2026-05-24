"""按 id 读取简历完整结构(含 parsed_json + raw_text)。

read_resume 是一个只读工具。和 ``list_user_resumes`` 是互补关系:
- list_user_resumes:紧凑 DTO,用来把"我最新的简历"消歧成 id
- read_resume:拿到 id 后,把整份简历(parsed_json + raw_text)拉给 Agent 作为事实依据

raw_text 不截断;如果未来 token 压力大,在工具层加可选 ``include_raw_text=false``。
"""

from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.agent.tool_adapter import BaseTool, ToolContext
from app.services.user_scope_service import get_resume_for_user_or_404


_BUSINESS_DETAIL_TO_ERROR_CLASS: dict[str, str] = {
    "Resume not found": "resume_not_found",
}

_BUSINESS_LLM_MESSAGES: dict[str, str] = {
    "resume_not_found": "请求的简历不存在;请让用户确认 resume_id,或先调用 list_user_resumes 查找。",
}


class ReadResumeToolArgs(BaseModel):
    resume_id: int = Field(..., description="要读取的简历 id。")


class ReadResumeTool(BaseTool):
    name = "read_resume"
    description = (
        "按 id 读取一份完整的简历记录,包括 title、raw_text、parsed_json、parse_status、"
        "source_type、content_hash、source_file_url、created_at、updated_at。"
        "当 Agent 需要基于具体简历的项目经历、技能、经验细节回答用户、或为后续动作工具"
        "提供事实依据时使用。优先级:list_user_resumes 找 id → read_resume 拉细节。"
        "已经在对话历史 / 摘要 / 之前工具结果里看到过完整字段时,不要重复调用。"
    )
    args_schema = ReadResumeToolArgs

    async def _execute(
        self,
        args: ReadResumeToolArgs,
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

        # 字段顺序与 schema ResumeRead 对齐,方便后续 format_response 直接用。
        return {
            "ok": True,
            "data": {
                "id": resume.id,
                "title": resume.title,
                "source_type": resume.source_type,
                "parse_status": resume.parse_status,
                "content_hash": resume.content_hash,
                "source_file_url": resume.source_file_url,
                "raw_text": resume.raw_text,
                "parsed_json": resume.parsed_json,
                "created_at": resume.created_at.isoformat() if resume.created_at else None,
                "updated_at": resume.updated_at.isoformat() if resume.updated_at else None,
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
