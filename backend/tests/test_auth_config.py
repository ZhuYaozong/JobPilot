"""认证配置必须在导入服务时拒绝不安全组合。"""
import os
from pathlib import Path
import subprocess
import sys

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def configured(**overrides):
    values = dict(app_env="production", app_debug=False, auth_dev_mode=False,
                  auth_secret_key="test-generated-" + "x" * 40, auth_algorithm="HS256")
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.mark.parametrize("environment", ["production", "staging", "service", "prodution"])
def test_service_modes_reject_dev_auth(environment):
    with pytest.raises(ValidationError, match="禁止 AUTH_DEV_MODE"):
        configured(app_env=environment, auth_dev_mode=True)


@pytest.mark.parametrize("environment", ["local", "test", " LOCAL "])
def test_explicit_dev_auth_only_in_local_test(environment):
    assert configured(app_env=environment, auth_dev_mode=True).auth_dev_mode


def test_dev_auth_default_is_off(monkeypatch):
    monkeypatch.delenv("AUTH_DEV_MODE", raising=False)
    assert not Settings(_env_file=None, app_env="local").auth_dev_mode


@pytest.mark.parametrize("changes", [
    {"app_debug": True},
    {"auth_secret_key": "jobpilot-dev-secret-change-in-production"},
    {"auth_secret_key": "change-this-to-a-long-random-secret"},
    {"auth_secret_key": "jobpilot-isolated-test-only"},
    {"auth_secret_key": "short"},
    {"auth_secret_key": " " * 40},
    {"auth_algorithm": "none"},
    {"app_env": " "},
])
def test_service_rejects_insecure_configuration(changes):
    with pytest.raises(ValidationError):
        configured(**changes)


def test_safe_service_configuration():
    assert configured().app_env == "production"


def test_unsafe_import_rejected_before_database_engine():
    # 子进程不读取仓库 .env，若校验前导入 sqlalchemy 则测试立即失败。
    script = '''
import importlib.abc, sys
class Block(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "sqlalchemy" or fullname.startswith("sqlalchemy."):
            raise AssertionError("engine imported before config rejection")
sys.meta_path.insert(0, Block())
from pydantic import ValidationError
try:
    import app.main
except ValidationError:
    print("configuration rejected before engine import")
else:
    raise AssertionError("unsafe service accepted")
'''
    env = {key: value for key, value in os.environ.items() if key.upper() not in {"PYTHONHOME", "PYTHONPATH", "__PYVENV_LAUNCHER__"}}
    env.update(APP_ENV="production", APP_DEBUG="false", AUTH_DEV_MODE="true",
               AUTH_SECRET_KEY="test-generated-" + "x" * 40,
               PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    result = subprocess.run([sys.executable, "-c", script], cwd=Path(__file__).resolve().parents[2], env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert "rejected before engine" in result.stdout
