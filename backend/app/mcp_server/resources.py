"""JobPilot MCP Server 的用户隔离资源模板。"""

from __future__ import annotations

import json

from app.agent.tools.read_job_posting_tool import ReadJobPostingTool
from app.agent.tools.read_resume_tool import ReadResumeTool
from app.mcp_server.tools import invoke_read_tool


async def resume_resource(resume_id: int) -> str:
    """以 JSON 资源返回当前用户的一份完整简历。"""
    data = await invoke_read_tool(ReadResumeTool, {"resume_id": resume_id})
    return json.dumps(data, ensure_ascii=False, default=str)


async def job_resource(job_id: int) -> str:
    """以 JSON 资源返回当前用户的一个完整岗位。"""
    data = await invoke_read_tool(
        ReadJobPostingTool,
        {"job_posting_id": job_id},
    )
    return json.dumps(data, ensure_ascii=False, default=str)
