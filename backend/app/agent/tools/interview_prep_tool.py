"""把 interview_prep_service.generate_interview_prep 包装成 Agent 工具。

中文说明：面试准备既可以由匹配页直接生成，也可以被模拟面试模式在工具链中调用。
工具层只做参数桥接、错误分类和返回值裁剪。
"""

from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel

from app.agent.tool_adapter import BaseTool, ToolContext, ToolSystemError
from app.llm.client import LLMClient
from app.schemas.interview_prep_generation import InterviewPrepGenerateRequest
from app.services.interview_prep_service import generate_interview_prep


_BUSINESS_DETAIL_TO_ERROR_CLASS: dict[str, str] = {
    "Resume not found": "resume_not_found",
    "Job posting not found": "job_posting_not_found",
    "Application record not found": "application_record_not_found",
    "Application record does not match resume and job posting": "application_resume_job_mismatch",
    "Resume needs parsing first": "resume_not_parsed",
    "Job posting needs parsing first": "job_posting_not_parsed",
    "Match analysis is required first": "match_result_missing",
    "Generated interview prep is empty": "llm_output_empty",
    "Generated interview prep must contain Chinese content": "llm_output_missing_chinese",
    "Generated interview prep is not specific enough": "llm_output_too_generic",
}

# 中文说明：message_for_llm 会进入 format_response prompt，应使用中文业务说明。
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
        "生成面试准备前需要先有匹配分析。请让用户先运行 analyze_match。"
    ),
    "llm_output_empty": "面试准备生成结果为空；请建议用户重试。",
    "llm_output_missing_chinese": (
        "面试准备草稿缺少要求的中文内容；请建议用户重试。"
    ),
    "llm_output_too_generic": (
        "面试准备草稿过于空泛；请建议用户补充更多上下文后重试。"
    ),
}


class InterviewPrepToolArgs(BaseModel):
    resume_id: int
    job_posting_id: int
    application_record_id: int | None = None


class InterviewPrepTool(BaseTool):
    name = "generate_interview_prep"
    description = (
        "为一组 resume + job_posting 生成面试准备提纲。两者必须已经解析，且该组合必须"
        "已经存在匹配分析(analyze_match)。application_record_id 可选；如果提供，必须"
        "与这组 resume/job 匹配。输出应为中文文本，覆盖岗位考察点、候选人优势、"
        "风险/短板、可能问题清单和准备建议。"
    )
    args_schema = InterviewPrepToolArgs

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm_client = llm_client

    async def _execute(
        self,
        args: InterviewPrepToolArgs,
        ctx: ToolContext,
    ) -> dict[str, Any]:
        # 中文说明：service 会要求 resume/job 已解析且同组 match result 已存在。
        request = InterviewPrepGenerateRequest(
            resume_id=args.resume_id,
            job_posting_id=args.job_posting_id,
            application_record_id=args.application_record_id,
        )
        try:
            artifact = await generate_interview_prep(
                ctx.db,
                request,
                current_user=ctx.current_user,
                llm_client=self._llm_client,
            )
        except HTTPException as exc:
            return self._http_exception_to_result(exc)

        # 中文说明：content_text 会进入最终回复，因此这里保留生成正文和最小元数据。
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
            # 中文说明：如“未解析”“缺匹配结果”属于用户可补前置条件的业务错误。
            return {
                "ok": False,
                "error_class": error_class,
                "message_for_llm": _BUSINESS_LLM_MESSAGES.get(error_class, detail),
                "user_facing_detail": detail,
            }

        if exc.status_code >= 500:
            # 中文说明：5xx 代表基础设施或模型调用失败，交给 workflow 标记运行失败。
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
