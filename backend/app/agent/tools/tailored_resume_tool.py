"""Wrap tailored_resume_service.generate_tailored_resume_version as a tool."""

from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel

from app.agent.tool_adapter import BaseTool, ToolContext, ToolSystemError
from app.llm.client import LLMClient
from app.schemas.tailored_resume_generation import TailoredResumeGenerateRequest
from app.services.tailored_resume_service import generate_tailored_resume_version


_BUSINESS_DETAIL_TO_ERROR_CLASS: dict[str, str] = {
    "Resume not found": "resume_not_found",
    "Job posting not found": "job_posting_not_found",
    "Application record not found": "application_record_not_found",
    "Application record does not match resume and job posting": "application_resume_job_mismatch",
    "Resume needs parsing first": "resume_not_parsed",
    "Job posting needs parsing first": "job_posting_not_parsed",
    "Match analysis is required first": "match_result_missing",
    "LLM response is not valid JSON": "llm_output_invalid",
    "LLM response does not match tailored resume schema": "llm_output_invalid",
    "Generated tailored resume is empty": "llm_output_empty",
    "Generated tailored resume label is empty": "llm_output_empty",
}

_BUSINESS_LLM_MESSAGES: dict[str, str] = {
    "resume_not_found": "The requested resume does not exist; ask the user for a valid resume_id.",
    "job_posting_not_found": "The requested job posting does not exist; ask the user for a valid job_posting_id.",
    "application_record_not_found": (
        "The requested application record does not exist; tell the user the id may be wrong."
    ),
    "application_resume_job_mismatch": (
        "The application record points to a different resume/job pair than requested. "
        "Ask the user to confirm which application/resume/job they want."
    ),
    "resume_not_parsed": "The resume has not been parsed; suggest running resume parsing first.",
    "job_posting_not_parsed": "The job posting has not been parsed; suggest running JD parsing first.",
    "match_result_missing": (
        "A match analysis is required before generating a tailored resume. Ask the user "
        "to run analyze_match first."
    ),
    "llm_output_invalid": "The tailored resume model returned invalid JSON; suggest retrying.",
    "llm_output_empty": "The tailored resume model returned empty content; suggest retrying.",
}


class TailoredResumeToolArgs(BaseModel):
    resume_id: int
    job_posting_id: int
    application_record_id: int | None = None


class TailoredResumeTool(BaseTool):
    name = "generate_tailored_resume"
    description = (
        "Generate a job-specific resume variant as a ResumeVersion for a parsed"
        " resume + parsed job posting pair. A latest match analysis for the pair"
        " must already exist; the tool looks it up by resume_id + job_posting_id."
        " application_record_id is optional and only used for validation if"
        " provided. Output is a Markdown resume version and a change summary."
    )
    args_schema = TailoredResumeToolArgs

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm_client = llm_client

    async def _execute(
        self,
        args: TailoredResumeToolArgs,
        ctx: ToolContext,
    ) -> dict[str, Any]:
        request = TailoredResumeGenerateRequest(
            resume_id=args.resume_id,
            job_posting_id=args.job_posting_id,
            application_record_id=args.application_record_id,
        )
        try:
            version = await generate_tailored_resume_version(
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
                "version_id": version.id,
                "resume_id": version.resume_id,
                "job_posting_id": version.job_posting_id,
                "version_no": version.version_no,
                "version_label": version.version_label,
                "content": version.content,
                "content_format": version.content_format,
                "source_type": version.source_type,
                "change_summary": version.change_summary,
                "is_active": version.is_active,
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

