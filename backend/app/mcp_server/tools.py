"""JobPilot MCP Server 暴露的只读工具。"""

from __future__ import annotations

from typing import Any

from app.agent.tool_adapter import BaseTool
from app.agent.tools.list_generated_artifacts_tool import ListGeneratedArtifactsTool
from app.agent.tools.list_user_applications_tool import ListUserApplicationsTool
from app.agent.tools.list_user_jobs_tool import ListUserJobsTool
from app.agent.tools.list_user_resumes_tool import ListUserResumesTool
from app.agent.tools.read_job_posting_tool import ReadJobPostingTool
from app.agent.tools.read_resume_tool import ReadResumeTool
from app.agent.tools.search_knowledge_tool import SearchKnowledgeTool
from app.mcp_server.context import authenticated_tool_context


async def invoke_read_tool(
    tool_cls: type[BaseTool],
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """复用现有 Tool Adapter，确保用户隔离、参数校验和审计一致。"""
    async with authenticated_tool_context() as tool_context:
        result = await tool_cls().invoke(arguments, tool_context)
    if not result.get("ok"):
        raise RuntimeError(
            result.get("user_facing_detail")
            or result.get("message_for_llm")
            or "JobPilot 工具执行失败",
        )
    return result.get("data") or {}


async def list_saved_jobs(query: str | None = None, limit: int = 20) -> dict[str, Any]:
    """列出当前用户保存在 JobPilot 中的岗位，可按公司或岗位标题过滤。"""
    return await invoke_read_tool(ListUserJobsTool, {"query": query, "limit": limit})


async def list_resumes(query: str | None = None, limit: int = 20) -> dict[str, Any]:
    """列出当前用户的简历，可按标题过滤。"""
    return await invoke_read_tool(ListUserResumesTool, {"query": query, "limit": limit})


async def list_applications(
    current_stage: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """列出当前用户的投递记录，可按阶段过滤。"""
    return await invoke_read_tool(
        ListUserApplicationsTool,
        {"current_stage": current_stage, "limit": limit},
    )


async def list_artifacts(
    resume_id: int | None = None,
    job_posting_id: int | None = None,
    artifact_type: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """列出当前用户已经生成的求职材料，不返回正文。"""
    return await invoke_read_tool(
        ListGeneratedArtifactsTool,
        {
            "resume_id": resume_id,
            "job_posting_id": job_posting_id,
            "artifact_type": artifact_type,
            "limit": limit,
        },
    )


async def read_resume(resume_id: int) -> dict[str, Any]:
    """读取当前用户指定简历的完整正文和结构化内容。"""
    return await invoke_read_tool(ReadResumeTool, {"resume_id": resume_id})


async def read_job_posting(job_posting_id: int) -> dict[str, Any]:
    """读取当前用户指定岗位的完整 JD 和结构化内容。"""
    return await invoke_read_tool(
        ReadJobPostingTool,
        {"job_posting_id": job_posting_id},
    )


async def search_knowledge(
    query: str,
    knowledge_base_id: int | None = None,
    top_k: int = 5,
) -> dict[str, Any]:
    """按当前 RAG 策略检索用户知识库。"""
    return await invoke_read_tool(
        SearchKnowledgeTool,
        {
            "query": query,
            "knowledge_base_id": knowledge_base_id,
            "top_k": top_k,
        },
    )
