"""把 cover_letter_service.generate_cover_letter 包装成 Agent 工具。

中文说明：求职信生成会写入 GeneratedArtifact，因此属于动作工具。这里负责把
service 层 HTTPException 分类成 Agent 能继续处理的业务错或系统错。

Mirrors MatchAnalysisTool's pattern: business errors come back as
``{"ok": False, "error_class": ..., ...}`` so the LLM can react; system errors
propagate as ``ToolSystemError`` to fail the agent run.
"""

from typing import Any, Literal

from fastapi import HTTPException
from pydantic import BaseModel

from app.agent.tool_adapter import BaseTool, ToolContext, ToolSystemError
from app.llm.client import LLMClient
from app.schemas.cover_letter_generation import CoverLetterGenerateRequest
from app.services.cover_letter_service import generate_cover_letter


_BUSINESS_DETAIL_TO_ERROR_CLASS: dict[str, str] = {
    "Resume not found": "resume_not_found",
    "Job posting not found": "job_posting_not_found",
    "Application record not found": "application_record_not_found",
    "Application record does not match resume and job posting": "application_resume_job_mismatch",
    "Resume needs parsing first": "resume_not_parsed",
    "Job posting needs parsing first": "job_posting_not_parsed",
    "Match analysis is required first": "match_result_missing",
    "Unsupported language_mode": "unsupported_language_mode",
    "Generated cover letter is empty": "llm_output_empty",
    "Generated cover letter must contain Chinese content": "llm_output_missing_chinese",
}

# 中文说明：这些提示只给 LLM 看，帮助它把内部错误转成下一步建议，而不是暴露 error_class。
_BUSINESS_LLM_MESSAGES: dict[str, str] = {
    "resume_not_found": "请求的简历不存在；请让用户提供有效的 resume_id。",
    "job_posting_not_found": "请求的岗位不存在；请让用户提供有效的 job_posting_id。",
    "application_record_not_found": (
        "请求的投递记录不存在；请提示用户 application_record_id 可能不正确。"
    ),
    "application_resume_job_mismatch": (
        "该投递记录关联的是另一组 resume/job。请让用户确认要使用哪个 application、resume 和 job。"
    ),
    "resume_not_parsed": "简历还没有解析；请建议用户先运行简历解析。",
    "job_posting_not_parsed": "岗位还没有解析；请建议用户先运行 JD 解析。",
    "match_result_missing": (
        "生成求职信前需要先有匹配分析。请让用户先运行 analyze_match。"
    ),
    "unsupported_language_mode": (
        "language_mode 必须是 'zh' 或 'bilingual'；请让用户选择其中一个。"
    ),
    "llm_output_empty": "求职信生成结果为空；请建议用户重试。",
    "llm_output_missing_chinese": (
        "求职信草稿缺少要求的中文内容；请建议用户重试。"
    ),
}


class CoverLetterToolArgs(BaseModel):
    resume_id: int
    job_posting_id: int
    application_record_id: int | None = None
    language_mode: Literal["zh", "bilingual"] = "zh"


class CoverLetterTool(BaseTool):
    name = "generate_cover_letter"
    description = (
        "为一组 resume + job_posting 生成求职信草稿。两者必须已经解析，且该组合必须"
        "已经存在匹配分析(analyze_match)。language_mode='zh' 表示只生成中文，"
        "language_mode='bilingual' 表示中文 + 英文。application_record_id 可选；"
        "如果提供，必须与这组 resume/job 匹配。"
    )
    args_schema = CoverLetterToolArgs

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm_client = llm_client

    async def _execute(
        self,
        args: CoverLetterToolArgs,
        ctx: ToolContext,
    ) -> dict[str, Any]:
        # 中文说明：application_record_id 是可选上下文，但如果传入会由 service 校验一致性。
        request = CoverLetterGenerateRequest(
            resume_id=args.resume_id,
            job_posting_id=args.job_posting_id,
            application_record_id=args.application_record_id,
            language_mode=args.language_mode,
        )
        try:
            artifact = await generate_cover_letter(
                ctx.db,
                request,
                current_user=ctx.current_user,
                llm_client=self._llm_client,
            )
        except HTTPException as exc:
            return self._http_exception_to_result(exc)

        # 中文说明：返回 artifact_id 与正文，方便 format_response 直接告诉用户产物已生成。
        return {
            "ok": True,
            "data": {
                "artifact_id": artifact.id,
                "artifact_type": artifact.artifact_type,
                "title": artifact.title,
                "content_text": artifact.content_text,
                "content_json": artifact.content_json,
                "resume_id": artifact.resume_id,
                "job_posting_id": artifact.job_posting_id,
                "application_record_id": artifact.application_record_id,
                "status": artifact.status,
                "generator_type": artifact.generator_type,
            },
        }

    def _http_exception_to_result(self, exc: HTTPException) -> dict[str, Any]:
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        error_class = _BUSINESS_DETAIL_TO_ERROR_CLASS.get(detail)

        if error_class is not None:
            # 中文说明：已知业务错返回 ok=false，保留本轮对话继续收束的机会。
            return {
                "ok": False,
                "error_class": error_class,
                "message_for_llm": _BUSINESS_LLM_MESSAGES.get(error_class, detail),
                "user_facing_detail": detail,
            }

        if exc.status_code >= 500:
            # 中文说明：模型服务不可用时失败 AgentRun，避免把基础设施问题伪装成用户可修复输入。
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
