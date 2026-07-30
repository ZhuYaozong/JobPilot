"""健康检查接口测试。"""

from unittest.mock import Mock

import torch
from fastapi.testclient import TestClient

from services.rag_models.app import app, runtime, settings


client = TestClient(app)


def test_health_returns_runtime_baseline_without_loading_models() -> None:
    """健康检查应报告运行时信息，但不能宣称模型已经加载。"""

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "JobPilot RAG Models"
    assert payload["configured_device"] == "cuda:0"
    assert payload["cuda_available"] is torch.cuda.is_available()
    assert payload["torch_version"] == torch.__version__
    assert payload["cuda_runtime"] == torch.version.cuda
    assert payload["models_loaded"] is False
    assert payload["model_error"] is None

    if torch.cuda.is_available():
        assert payload["device_name"] == torch.cuda.get_device_name(0)
    else:
        assert payload["device_name"] is None


def test_ready_returns_503_before_models_are_loaded() -> None:
    """进程存活但模型未加载时，readiness 必须明确失败。"""

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "models_loaded": False,
        "model_error": None,
    }


def test_lifespan_calls_runtime_load_and_unload(monkeypatch) -> None:
    """应用生命周期应成对调用模型加载和释放。"""

    load_mock = Mock()
    unload_mock = Mock()
    monkeypatch.setattr(settings, "load_models_on_startup", True)
    monkeypatch.setattr(runtime, "load", load_mock)
    monkeypatch.setattr(runtime, "unload", unload_mock)

    with TestClient(app) as lifecycle_client:
        assert lifecycle_client.get("/health").status_code == 200

    load_mock.assert_called_once_with()
    unload_mock.assert_called_once_with()
