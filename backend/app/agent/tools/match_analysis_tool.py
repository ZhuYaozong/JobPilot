"""把 match_analysis_service.analyze_match 包装成 Agent 工具。

中文说明：这里不重新实现匹配分析，只把 HTTP/service 层的异常语义翻译成
Agent 能理解的三类结果：业务错返回 ok=false，系统错抛 ToolSystemError。

The underlying service raises ``HTTPException`` for both business errors
(404/400: resource missing, not parsed, schema mismatch) and infrastructure
errors (500/502: LLM config missing, LLM network failure). We classify each
case here so the agent layer can react accordingly.
"""

from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel

from app.agent.tool_adapter import BaseTool, ToolContext, ToolSystemError
from app.llm.client import LLMClient
from app.schemas.match_analysis import MatchAnalysisRequest
from app.services.match_analysis_service import analyze_match


# 中文说明：业务 service 的 detail 是错误分类入口，修改 service 文案时必须同步测试。
# Detail strings come from match_analysis_service.analyze_match. We pin them
# here so a future copy-edit in the service does not silently break agent
# error classification — the test suite will fail if these drift.
_BUSINESS_DETAIL_TO_ERROR_CLASS: dict[str, str] = {
    "Resume not found": "resume_not_found",
    "Job posting not found": "job_posting_not_found",
    "Resume needs parsing first": "resume_not_parsed",
    "Job posting needs parsing first": "job_posting_not_parsed",
    "LLM response is not valid JSON": "llm_output_invalid",
    "LLM response does not match match analysis schema": "llm_output_invalid",
}

_BUSINESS_LLM_MESSAGES: dict[str, str] = {
    "resume_not_found": (
        "请求的简历不存在。请让用户选择一个有效的 resume_id。"
    ),
    "job_posting_not_found": (
        "请求的岗位不存在。请让用户选择一个有效的 job_posting_id。"
    ),
    "resume_not_parsed": (
        "这份简历还没有完成结构化解析。请建议用户先运行简历解析，再请求匹配分析。"
    ),
    "job_posting_not_parsed": (
        "这个岗位还没有完成 JD 解析。请建议用户先运行 JD 解析，再请求匹配分析。"
    ),
    "llm_output_invalid": (
        "匹配分析模型返回了无法解析的输出。请建议用户稍后重试。"
    ),
}


class MatchAnalysisToolArgs(BaseModel):
    resume_id: int
    job_posting_id: int


class MatchAnalysisTool(BaseTool):
    name = "analyze_match"
    description = (
        "为已解析的简历和已解析的岗位生成匹配分析。返回 overall_score(0-100)、"
        "strengths、weaknesses、missing_keywords、suggestions。"
        "resume 和 job_posting 必须已经完成解析，即 parsed_json 已有内容。"
    )
    args_schema = MatchAnalysisToolArgs

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm_client = llm_client

    async def _execute(
        self,
        args: MatchAnalysisToolArgs,
        ctx: ToolContext,
    ) -> dict[str, Any]:
        # 中文说明：工具层把 Pydantic args 转成 service request，真实校验仍由 service 完成。
        request = MatchAnalysisRequest(
            resume_id=args.resume_id,
            job_posting_id=args.job_posting_id,
        )
        try:
            match = await analyze_match(
                ctx.db,
                request,
                current_user=ctx.current_user,
                llm_client=self._llm_client,
            )
        except HTTPException as exc:
            return self._http_exception_to_result(exc)

        # 中文说明：只返回 Agent 后续生成回复需要的结构化字段，不返回 ORM 对象。
        return {
            "ok": True,
            "data": {
                "match_id": match.id,
                "resume_id": match.resume_id,
                "job_posting_id": match.job_posting_id,
                "overall_score": match.overall_score,
                "strengths": list(match.strengths or []),
                "weaknesses": list(match.weaknesses or []),
                "missing_keywords": list(match.missing_keywords or []),
                "suggestions": list(match.suggestions or []),
            },
        }

    def _http_exception_to_result(self, exc: HTTPException) -> dict[str, Any]:
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        error_class = _BUSINESS_DETAIL_TO_ERROR_CLASS.get(detail)

        if error_class is not None:
            # 中文说明：已知 4xx/输出校验类错误让模型以用户友好方式解释或引导下一步。
            return {
                "ok": False,
                "error_class": error_class,
                "message_for_llm": _BUSINESS_LLM_MESSAGES.get(error_class, detail),
                "user_facing_detail": detail,
            }

        # 中文说明：LLM 配置或远端失败不是模型换参数能解决的，升级为系统错误。
        # 500 LLM config / 502 LLM call — not LLM-fixable, treat as system.
        if exc.status_code >= 500:
            raise ToolSystemError(
                self.name,
                error_class="llm_unavailable" if exc.status_code == 502 else "llm_config_missing",
                detail=detail,
            )

        # 中文说明：未知 4xx 保守当业务错返回，避免单个新 detail 让整轮 Agent 崩溃。
        # Unknown 4xx — surface as generic business error rather than crash.
        return {
            "ok": False,
            "error_class": "unknown_business_error",
            "message_for_llm": detail,
            "user_facing_detail": detail,
        }
