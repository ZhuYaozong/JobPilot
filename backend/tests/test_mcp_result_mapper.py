"""MCP 工具结果的安全映射测试。"""

from mcp.types import CallToolResult, TextContent

from app.mcp.result_mapper import UNTRUSTED_DATA_NOTICE, map_mcp_tool_result


def test_map_structured_result_keeps_security_notice() -> None:
    result = CallToolResult(
        content=[TextContent(type="text", text="找到 1 个岗位")],
        structuredContent={"jobs": [{"title": "AI Engineer"}]},
        isError=False,
    )
    mapped = map_mcp_tool_result(
        result,
        server_id="jobs",
        tool_name="search_jobs",
        max_chars=2_000,
    )
    assert mapped["ok"] is True
    assert mapped["data"]["structured_content"]["jobs"][0]["title"] == "AI Engineer"
    assert mapped["data"]["security_notice"] == UNTRUSTED_DATA_NOTICE


def test_map_result_truncates_large_external_content() -> None:
    result = CallToolResult(
        content=[TextContent(type="text", text="x" * 2_000)],
        structuredContent={"raw": "y" * 2_000},
        isError=False,
    )
    mapped = map_mcp_tool_result(
        result,
        server_id="jobs",
        tool_name="search_jobs",
        max_chars=1_000,
    )
    assert mapped["data"]["truncated"] is True
    assert len(mapped["data"]["text_content"]) < 1_100
    assert mapped["data"]["structured_content"]["truncated"] is True


def test_map_is_error_to_business_error() -> None:
    result = CallToolResult(
        content=[TextContent(type="text", text="upstream rejected query")],
        isError=True,
    )
    mapped = map_mcp_tool_result(
        result,
        server_id="jobs",
        tool_name="search_jobs",
        max_chars=2_000,
    )
    assert mapped["ok"] is False
    assert mapped["error_class"] == "mcp_tool_execution_error"
