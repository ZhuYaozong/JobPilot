"""Tool registry.

Workflow code routes by ``state["tool_name"]`` through this dict. Adding a new
tool is a two-line change here plus one new module under ``tools/``.
"""

from app.agent.tool_adapter import BaseTool
from app.agent.tools.cover_letter_tool import CoverLetterTool
from app.agent.tools.interview_prep_tool import InterviewPrepTool
from app.agent.tools.match_analysis_tool import MatchAnalysisTool

TOOL_REGISTRY: dict[str, type[BaseTool]] = {
    MatchAnalysisTool.name: MatchAnalysisTool,
    CoverLetterTool.name: CoverLetterTool,
    InterviewPrepTool.name: InterviewPrepTool,
}

__all__ = [
    "TOOL_REGISTRY",
    "CoverLetterTool",
    "InterviewPrepTool",
    "MatchAnalysisTool",
]
