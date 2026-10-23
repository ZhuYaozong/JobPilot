"""护栏独立验证：可以直接运行本文件，不加载 pytest conftest 或连接数据库。"""
import importlib.abc
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from testing_environment import (
    TestEnvironmentError as GuardError, configure_test_environment,
    isolated_settings_directory, validate_database_url,
)

SAFE = "postgresql+asyncpg://jobpilot_test:disposable@127.0.0.1:35432/jobpilot_test"


class EnvironmentGuardTests(unittest.TestCase):
    def test_valid_target(self):
        self.assertEqual(validate_database_url({"TEST_DATABASE_URL": SAFE}), SAFE)

    def test_missing_does_not_fall_back(self):
        with self.assertRaises(GuardError):
            validate_database_url({"DATABASE_URL": SAFE})

    def test_rejects_other_targets_and_options(self):
        invalid = [
            "", "not-a-url", SAFE.replace("35432", "25432"),
            SAFE.replace("35432", "invalid"),
            SAFE.replace("127.0.0.1", "localhost"),
            SAFE.replace("127.0.0.1", "192.168.1.10"),
            SAFE.replace("jobpilot_test:", "postgres:"),
            SAFE.replace("/jobpilot_test", "/jobpilot"),
            SAFE.replace("disposable", ""),
            SAFE + "?host=production", SAFE + "#fragment",
            " " + SAFE, SAFE.replace("postgresql+asyncpg", "postgresql"),
        ]
        for url in invalid:
            with self.subTest(url=url):
                with self.assertRaises(GuardError) as error:
                    validate_database_url({"TEST_DATABASE_URL": url})
                self.assertNotIn("disposable", str(error.exception))

    def test_configuration_is_validated_before_mutation(self):
        with patch.dict(os.environ, {"DATABASE_URL": "unchanged"}, clear=True):
            with self.assertRaises(GuardError):
                configure_test_environment()
            self.assertEqual(os.environ["DATABASE_URL"], "unchanged")

    def test_replaces_inherited_service_configuration(self):
        with patch.dict(os.environ, {
            "TEST_DATABASE_URL": SAFE, "DATABASE_URL": "business",
            "LLM_API_KEY": "real-secret", "MCP_ENABLED": "true",
        }, clear=True):
            configure_test_environment()
            self.assertEqual(os.environ["DATABASE_URL"], SAFE)
            self.assertEqual(os.environ["LLM_API_KEY"], "test-only")
            self.assertEqual(os.environ["MCP_ENABLED"], "false")

    def test_settings_directory_is_empty_and_restored_on_failure(self):
        previous = Path.cwd()
        with self.assertRaisesRegex(RuntimeError, "probe"):
            with isolated_settings_directory():
                self.assertFalse(Path(".env").exists())
                self.assertNotEqual(Path.cwd(), previous)
                raise RuntimeError("probe")
        self.assertEqual(Path.cwd(), previous)

    def test_invalid_pytest_startup_never_imports_application_or_engine(self):
        # 如果 conftest 在护栏之前导入应用/数据库引擎，探针立即使测试失败。
        probe = """
import importlib.abc, runpy, sys
from pathlib import Path
backend = Path(sys.argv[1])
sys.path.insert(0, str(backend))
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'app' or fullname.startswith('app.') or fullname.startswith('sqlalchemy'):
            raise AssertionError('unsafe import before guard: ' + fullname)
sys.meta_path.insert(0, Block())
from testing_environment import TestEnvironmentError
try:
    runpy.run_path(str(backend / 'tests' / 'conftest.py'))
except TestEnvironmentError:
    print('guard rejected before application/engine import')
else:
    raise AssertionError('guard did not reject')
"""
        for value in (None, SAFE.replace("35432", "25432"), SAFE + "?host=production"):
            with self.subTest(value=value):
                env = os.environ.copy()
                env.pop("TEST_DATABASE_URL", None)
                env["DATABASE_URL"] = SAFE
                env["PYTHONDONTWRITEBYTECODE"] = "1"
                if value is not None:
                    env["TEST_DATABASE_URL"] = value
                result = subprocess.run(
                    [sys.executable, "-c", probe, str(BACKEND)],
                    env=env, capture_output=True, text=True, timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("guard rejected", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)



def test_network_guard_blocks_non_database_connections():
    """验证实际 fixture 会在尝试真实模型连接前拒绝。"""
    import socket
    import pytest

    with socket.socket() as connection:
        with pytest.raises(RuntimeError, match="Test network blocked"):
            connection.connect(("127.0.0.1", 9))


def test_relative_artifacts_use_pytest_directory(tmp_path):
    """相对输出不得写回仓库或用户文件目录。"""
    assert Path.cwd() == tmp_path
    output = Path("guard-probe.txt")
    output.write_text("test-only", encoding="utf-8")
    assert (tmp_path / output).read_text(encoding="utf-8") == "test-only"


def test_asyncio_internal_socketpair_remains_available():
    """Windows 事件循环可用，同时没有放开普通本机网络连接。"""
    import asyncio

    async def probe():
        await asyncio.sleep(0)
        return "ok"

    assert asyncio.run(probe()) == "ok"
