"""Wrap match_analysis_service.analyze_match as a tool the agent can call.

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
        "The requested resume does not exist. Ask the user to pick a valid resume_id."
    ),
    "job_posting_not_found": (
        "The requested job posting does not exist. Ask the user to pick a valid"
        " job_posting_id."
    ),
    "resume_not_parsed": (
        "The resume has not been parsed yet. Suggest the user run resume parsing"
        " before requesting a match analysis."
    ),
    "job_posting_not_parsed": (
        "The job posting has not been parsed yet. Suggest the user run JD parsing"
        " before requesting a match analysis."
    ),
    "llm_output_invalid": (
        "The matching model returned an output that could not be parsed. Try again"
        " or suggest the user retry shortly."
    ),
}


class MatchAnalysisToolArgs(BaseModel):
    resume_id: int
    job_posting_id: int


class MatchAnalysisTool(BaseTool):
    name = "analyze_match"
    description = (
        "Generate a match analysis between a parsed resume and a parsed job"
        " posting. Returns overall_score (0-100), strengths, weaknesses,"
        " missing_keywords, and suggestions. Both resume and job posting must"
        " already be parsed (their parsed_json fields populated)."
    )
    args_schema = MatchAnalysisToolArgs

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm_client = llm_client

    async def _execute(
        self,
        args: MatchAnalysisToolArgs,
        ctx: ToolContext,
    ) -> dict[str, Any]:
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
            return {
                "ok": False,
                "error_class": error_class,
                "message_for_llm": _BUSINESS_LLM_MESSAGES.get(error_class, detail),
                "user_facing_detail": detail,
            }

        # 500 LLM config / 502 LLM call — not LLM-fixable, treat as system.
        if exc.status_code >= 500:
            raise ToolSystemError(
                self.name,
                error_class="llm_unavailable" if exc.status_code == 502 else "llm_config_missing",
                detail=detail,
            )

        # Unknown 4xx — surface as generic business error rather than crash.
        return {
            "ok": False,
            "error_class": "unknown_business_error",
            "message_for_llm": detail,
            "user_facing_detail": detail,
        }
