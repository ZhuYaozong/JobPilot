"""只供测试使用的启动护栏；不得从生产应用导入。"""
from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
import tempfile
from urllib.parse import urlsplit, unquote


class TestEnvironmentError(RuntimeError):
    """测试配置未满足隔离约束。"""


def validate_database_url(environ: dict[str, str]) -> str:
    """先验证目标，再允许导入应用；错误信息不回显凭据。"""
    raw = environ.get("TEST_DATABASE_URL", "")
    try:
        url = urlsplit(raw)
        valid = (
            url.scheme == "postgresql+asyncpg"
            and url.hostname == "127.0.0.1"
            and url.port == 35432
            and unquote(url.username or "") == "jobpilot_test"
            and bool(url.password)
            and url.path == "/jobpilot_test"
            and not url.query
            and not url.fragment
            and raw == raw.strip()
        )
    except (ValueError, TypeError):
        valid = False
    if not valid:
        raise TestEnvironmentError(
            "TEST_DATABASE_URL must target "
            "postgresql+asyncpg://jobpilot_test:<password>@127.0.0.1:35432/jobpilot_test "
            "without URL options; application DATABASE_URL is never a fallback."
        )
    return raw


def configure_test_environment() -> str:
    """覆盖继承的业务配置；只影响当前测试进程。"""
    database_url = validate_database_url(dict(os.environ))
    os.environ.update({
        "DATABASE_URL": database_url,
        "APP_ENV": "test",
        "APP_DEBUG": "false",
        "AUTH_DEV_MODE": "true",  # 兼容既有身份夹具，不更改生产默认值。
        "AUTH_SECRET_KEY": "jobpilot-isolated-test-only",
        "REDIS_URL": "redis://127.0.0.1:9/0",
        "LLM_BASE_URL": "http://127.0.0.1:9/v1",
        "LLM_API_KEY": "test-only",
        "LLM_MODEL_NAME": "test-only",
        "EMBEDDING_BASE_URL": "http://127.0.0.1:9/v1",
        "EMBEDDING_API_KEY": "test-only",
        "EMBEDDING_MODEL_NAME": "test-only",
        "RERANKER_BASE_URL": "http://127.0.0.1:9",
        "RERANKER_API_KEY": "test-only",
        "RERANKER_MODEL_NAME": "test-only",
        "MCP_ENABLED": "false",
        "MCP_SERVERS_JSON": "[]",
    })
    return database_url


@contextmanager
def isolated_settings_directory():
    """从空目录首次加载 Settings，避免读取仓库中的 .env。"""
    previous = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="jobpilot-test-settings-") as folder:
        os.chdir(folder)
        try:
            yield
        finally:
            os.chdir(previous)


def migrate_test_database() -> None:
    """仅向通过护栏的专用测试库执行已有迁移。"""
    configure_test_environment()
    with isolated_settings_directory():
        from app.core.config import settings
    assert settings.database_url == os.environ["TEST_DATABASE_URL"]
    from alembic import command
    from alembic.config import Config

    command.upgrade(Config(str(Path(__file__).parent / "alembic.ini")), "head")


if __name__ == "__main__":
    import sys
    if sys.argv[1:] != ["migrate"]:
        raise SystemExit("Usage: python testing_environment.py migrate")
    migrate_test_database()
