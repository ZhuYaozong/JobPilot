"""MCP 远程服务器配置解析与基础安全校验。"""

from __future__ import annotations

import ipaddress
import json
import re
from urllib.parse import urlparse

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from app.core.config import settings


_SERVER_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,47}$")
_LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost"}


class MCPConfigError(ValueError):
    """MCP 配置不合法。"""


class MCPRemoteServerConfig(BaseModel):
    """一个由管理员配置的远程 MCP Server。"""

    id: str
    url: str
    enabled: bool = True
    allowed_tools: list[str] = Field(default_factory=list)
    auth_token_env: str | None = None
    discovery_timeout_seconds: float | None = Field(default=None, gt=0, le=60)
    call_timeout_seconds: float | None = Field(default=None, gt=0, le=300)
    max_result_chars: int | None = Field(default=None, ge=1_000, le=100_000)
    category: str = "general"

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if not _SERVER_ID_PATTERN.fullmatch(value):
            raise ValueError("id 必须以小写字母开头，且只能包含小写字母、数字和下划线")
        return value

    @field_validator("allowed_tools")
    @classmethod
    def normalize_allowed_tools(cls, value: list[str]) -> list[str]:
        # 保持配置顺序并去重；空列表代表不暴露任何工具，而不是“全部允许”。
        return list(dict.fromkeys(item.strip() for item in value if item.strip()))

    @model_validator(mode="after")
    def validate_url_policy(self) -> "MCPRemoteServerConfig":
        parsed = urlparse(self.url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("url 必须是有效的 http/https Streamable HTTP 地址")
        if parsed.username or parsed.password:
            raise ValueError("url 不允许内嵌用户名或密码")
        if settings.app_env == "production" and parsed.scheme != "https":
            raise ValueError("生产环境 MCP Server 必须使用 HTTPS")
        if parsed.scheme == "http" and parsed.hostname not in _LOCAL_HOSTS:
            raise ValueError("非 HTTPS MCP Server 只允许 localhost")
        if _is_forbidden_literal_ip(parsed.hostname):
            raise ValueError("不允许连接未显式批准的私有或特殊 IP 地址")
        return self

    @property
    def technical_prefix(self) -> str:
        return f"mcp__{self.id}__"

    @property
    def discovery_timeout(self) -> float:
        return self.discovery_timeout_seconds or settings.mcp_discovery_timeout_seconds

    @property
    def call_timeout(self) -> float:
        return self.call_timeout_seconds or settings.mcp_call_timeout_seconds

    @property
    def result_limit(self) -> int:
        return self.max_result_chars or settings.mcp_max_result_chars


def _is_forbidden_literal_ip(hostname: str) -> bool:
    """拒绝直接写入配置的私网/链路本地等特殊 IP，localhost 明确例外。"""
    if hostname in _LOCAL_HOSTS:
        return False
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return False
    return not address.is_global


def load_mcp_server_configs() -> list[MCPRemoteServerConfig]:
    """从环境 JSON 读取启用且配置了白名单的 MCP Server。"""
    if not settings.mcp_enabled:
        return []
    try:
        raw = json.loads(settings.mcp_servers_json)
    except json.JSONDecodeError as exc:
        raise MCPConfigError(f"MCP_SERVERS_JSON 不是合法 JSON: {exc}") from exc
    if not isinstance(raw, list):
        raise MCPConfigError("MCP_SERVERS_JSON 顶层必须是数组")
    try:
        configs = [MCPRemoteServerConfig.model_validate(item) for item in raw]
    except ValidationError as exc:
        raise MCPConfigError(f"MCP Server 配置不合法: {exc}") from exc

    ids = [item.id for item in configs]
    if len(ids) != len(set(ids)):
        raise MCPConfigError("MCP Server id 不能重复")
    return [item for item in configs if item.enabled and item.allowed_tools]
