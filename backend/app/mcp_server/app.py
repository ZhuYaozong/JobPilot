"""独立部署的 JobPilot 只读 Streamable HTTP MCP Server。"""

from __future__ import annotations

from urllib.parse import urlparse

from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from pydantic import AnyHttpUrl

from app.core.config import settings
from app.mcp_server.auth import JobPilotTokenVerifier
from app.mcp_server.resources import job_resource, resume_resource
from app.mcp_server.tools import (
    list_applications,
    list_artifacts,
    list_resumes,
    list_saved_jobs,
    read_job_posting,
    read_resume,
    search_knowledge,
)


def _allowed_hosts() -> list[str]:
    parsed = urlparse(settings.mcp_server_public_url)
    values = {"127.0.0.1", "localhost"}
    if parsed.hostname:
        values.add(parsed.hostname)
        if parsed.port:
            values.add(f"{parsed.hostname}:{parsed.port}")
    return sorted(values)


mcp = FastMCP(
    name="JobPilot",
    instructions=(
        "读取当前用户在 JobPilot 中保存的岗位、简历、投递记录、材料和知识库。"
        "本服务只暴露只读能力。"
    ),
    host=settings.mcp_server_host,
    port=settings.mcp_server_port,
    streamable_http_path="/mcp",
    json_response=True,
    stateless_http=True,
    token_verifier=JobPilotTokenVerifier(),
    auth=AuthSettings(
        issuer_url=AnyHttpUrl(settings.mcp_server_issuer_url),
        resource_server_url=AnyHttpUrl(settings.mcp_server_public_url),
        required_scopes=["jobpilot:read"],
    ),
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=_allowed_hosts(),
        allowed_origins=[],
    ),
)

_READ_ONLY = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)

mcp.tool(name="list_saved_jobs", annotations=_READ_ONLY)(list_saved_jobs)
mcp.tool(name="list_resumes", annotations=_READ_ONLY)(list_resumes)
mcp.tool(name="list_applications", annotations=_READ_ONLY)(list_applications)
mcp.tool(name="list_artifacts", annotations=_READ_ONLY)(list_artifacts)
mcp.tool(name="read_resume", annotations=_READ_ONLY)(read_resume)
mcp.tool(name="read_job_posting", annotations=_READ_ONLY)(read_job_posting)
mcp.tool(name="search_knowledge", annotations=_READ_ONLY)(search_knowledge)

mcp.resource(
    "jobpilot://resumes/{resume_id}",
    name="jobpilot-resume",
    title="JobPilot Resume",
    description="当前认证用户的一份完整简历 JSON。",
    mime_type="application/json",
)(resume_resource)
mcp.resource(
    "jobpilot://jobs/{job_id}",
    name="jobpilot-job",
    title="JobPilot Job Posting",
    description="当前认证用户的一个完整岗位 JSON。",
    mime_type="application/json",
)(job_resource)

# 独立 ASGI 入口：uvicorn app.mcp_server.app:app --host 127.0.0.1 --port 8001
app = mcp.streamable_http_app()
