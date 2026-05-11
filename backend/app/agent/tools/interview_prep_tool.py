"""Wrap interview_prep_service.generate_interview_prep as an agent tool."""

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

_BUSINESS_LLM_MESSAGES: dict[str, str] = {
    "resume_not_found": "The requested resume does not exist; ask the user for a valid resume_id.",
    "job_posting_not_found": "The requested job posting does not exist; ask the user for a valid job_posting_id.",
    "application_record_not_found": (
        "The requested application record does not exist; tell the user the id may be wrong."
    ),
    "application_resume_job_mismatch": (
        "The application record points to a different resume/job pair than the one requested. "
        "Ask the user to confirm which application/resume/job they want."
    ),
    "resume_not_parsed": "The resume has not been parsed; suggest running resume parsing first.",
    "job_posting_not_parsed": "The job posting has not been parsed; suggest running JD parsing first.",
    "match_result_missing": (
        "A match analysis is required before drafting interview prep. Ask the user to run "
        "analyze_match first."
    ),
    "llm_output_empty": "Interview prep generation returned empty content; suggest the user retry.",
    "llm_output_missing_chinese": (
        "The interview prep draft was missing the requested Chinese content; suggest the user retry."
    ),
    "llm_output_too_generic": (
        "The interview prep draft was too generic; suggest the user retry with more context."
    ),
}


class InterviewPrepToolArgs(BaseModel):
    resume_id: int
    job_posting_id: int
    application_record_id: int | None = None


class InterviewPrepTool(BaseTool):
    name = "generate_interview_prep"
    description = (
        "Generate an interview preparation outline for a resume + job posting pair."
        " Both must already be parsed, and a match analysis (analyze_match) must"
        " exist for the pair first. application_record_id is optional; if provided"
        " it must match the resume/job pair. Output is Chinese text covering 岗位"
        "考察点、候选人优势、风险/短板、可能问题清单 和 准备建议。"
    )
    args_schema = InterviewPrepToolArgs

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm_client = llm_client

    async def _execute(
        self,
        args: InterviewPrepToolArgs,
        ctx: ToolContext,
    ) -> dict[str, Any]:
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
