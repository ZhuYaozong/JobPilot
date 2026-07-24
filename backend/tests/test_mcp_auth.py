"""MCP 专用 token 的 audience/scope 边界测试。"""

import asyncio

from fastapi.testclient import TestClient
from jose import JWTError
import pytest

from app.core.security import decode_mcp_access_token
from app.mcp_server.auth import JobPilotTokenVerifier


def test_issue_mcp_token_is_resource_bound(client: TestClient) -> None:
    response = client.post("/api/auth/mcp-token")
    assert response.status_code == 200
    body = response.json()
    assert body["scopes"] == ["jobpilot:read"]
    payload = decode_mcp_access_token(body["access_token"])
    assert payload["scope"] == "jobpilot:read"
    assert payload["aud"] == body["resource"]
    verified = asyncio.run(
        JobPilotTokenVerifier().verify_token(body["access_token"]),
    )
    assert verified is not None
    assert verified.subject == payload["sub"]
    assert verified.scopes == ["jobpilot:read"]


def test_regular_api_token_cannot_be_used_as_mcp_token(
    client: TestClient,
    test_marker: str,
) -> None:
    response = client.post(
        "/api/auth/register",
        json={"username": test_marker, "password": "mcp-test-pass"},
    )
    assert response.status_code == 201
    with pytest.raises(JWTError):
        decode_mcp_access_token(response.json()["access_token"])
