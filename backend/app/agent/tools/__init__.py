"""Tool registry.

Workflow code routes by ``state["tool_name"]`` through this dict. Adding a new
tool is a two-line change here plus one new module under ``tools/``.

Tools fall into three rough categories:

- **Read tools** (``list_user_*``): cheap, no LLM, no side effects. Used by
  the agent to resolve vague references like "我最新的简历" or "腾讯的岗位"
  into concrete IDs before calling action tools. Cheap enough that we let the
  ReAct loop call them freely.
- **Retrieval tools** (``search_knowledge``): semantic search over the user's
  uploaded knowledge base content. One embedding call per invocation.
- **Action tools** (``analyze_match``, ``generate_cover_letter``,
  ``generate_interview_prep``): call the underlying business service, take
  seconds, write rows. Each typically called once per turn.
"""

from app.agent.tool_adapter import BaseTool
from app.agent.tools.cover_letter_tool import CoverLetterTool
from app.agent.tools.interview_prep_tool import InterviewPrepTool
from app.agent.tools.list_user_applications_tool import ListUserApplicationsTool
from app.agent.tools.list_user_jobs_tool import ListUserJobsTool
from app.agent.tools.list_user_resumes_tool import ListUserResumesTool
from app.agent.tools.match_analysis_tool import MatchAnalysisTool
from app.agent.tools.search_knowledge_tool import SearchKnowledgeTool

TOOL_REGISTRY: dict[str, type[BaseTool]] = {
    ListUserJobsTool.name: ListUserJobsTool,
    ListUserResumesTool.name: ListUserResumesTool,
    ListUserApplicationsTool.name: ListUserApplicationsTool,
    SearchKnowledgeTool.name: SearchKnowledgeTool,
    MatchAnalysisTool.name: MatchAnalysisTool,
    CoverLetterTool.name: CoverLetterTool,
    InterviewPrepTool.name: InterviewPrepTool,
}

__all__ = [
    "TOOL_REGISTRY",
    "CoverLetterTool",
    "InterviewPrepTool",
    "ListUserApplicationsTool",
    "ListUserJobsTool",
    "ListUserResumesTool",
    "MatchAnalysisTool",
    "SearchKnowledgeTool",
]
