"""JobPilot 入站 MCP Server 的公开契约测试。"""

from app.mcp_server.app import mcp


def test_mcp_server_exposes_only_read_tools() -> None:
    tools = mcp._tool_manager.list_tools()
    names = {tool.name for tool in tools}
    assert names == {
        "list_saved_jobs",
        "list_resumes",
        "list_applications",
        "list_artifacts",
        "read_resume",
        "read_job_posting",
        "search_knowledge",
    }
    for tool in tools:
        assert tool.annotations is not None
        assert tool.annotations.readOnlyHint is True
        assert tool.annotations.destructiveHint is False


def test_mcp_server_exposes_user_scoped_resource_templates() -> None:
    templates = mcp._resource_manager.list_templates()
    uris = {str(item.uri_template) for item in templates}
    assert "jobpilot://resumes/{resume_id}" in uris
    assert "jobpilot://jobs/{job_id}" in uris
