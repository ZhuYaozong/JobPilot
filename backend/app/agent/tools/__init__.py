"""Tool registry. Slice 3 ships with one tool; slice 4 will register more.

Workflow code routes by ``state["tool_name"]`` through this dict. Adding a new
tool is a two-line change here plus one new module under ``tools/``.
"""

from app.agent.tool_adapter import BaseTool
from app.agent.tools.match_analysis_tool import MatchAnalysisTool

TOOL_REGISTRY: dict[str, type[BaseTool]] = {
    MatchAnalysisTool.name: MatchAnalysisTool,
}

__all__ = ["TOOL_REGISTRY", "MatchAnalysisTool"]
