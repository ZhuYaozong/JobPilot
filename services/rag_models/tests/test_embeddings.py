"""OpenAI-compatible Embedding 接口测试。"""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from services.rag_models.app import app, runtime
from services.rag_models.model_runtime import EmbeddingInferenceResult


client = TestClient(app)


@pytest.fixture
def loaded_runtime(monkeypatch):
    """用轻量假对象模拟两个模型已经完成加载。"""

    monkeypatch.setattr(runtime, "_embedder", object())
    monkeypatch.setattr(runtime, "_reranker", object())


def test_embeddings_returns_503_when_models_are_not_ready() -> None:
    """模型未就绪时不能接受推理请求。"""

    response = client.post(
        "/v1/embeddings",
        json={"model": "BAAI/bge-m3", "input": ["Python 后端"]},
    )

    assert response.status_code == 503


def test_embeddings_preserves_batch_order(loaded_runtime, monkeypatch) -> None:
    """批量向量必须按输入顺序返回，并包含真实 token usage。"""

    vectors = [
        [0.1] * 1024,
        [0.2] * 1024,
    ]
    embed_mock = Mock(
        return_value=EmbeddingInferenceResult(vectors=vectors, prompt_tokens=9)
    )
    monkeypatch.setattr(runtime, "embed", embed_mock)

    texts = ["Python 后端", "产品运营"]
    response = client.post(
        "/v1/embeddings",
        json={
            "model": "BAAI/bge-m3",
            "input": texts,
            "dimensions": 1024,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["object"] == "list"
    assert payload["model"] == "BAAI/bge-m3"
    assert [item["index"] for item in payload["data"]] == [0, 1]
    assert payload["data"][0]["embedding"] == vectors[0]
    assert payload["data"][1]["embedding"] == vectors[1]
    assert payload["usage"] == {"prompt_tokens": 9, "total_tokens": 9}
    embed_mock.assert_called_once_with(texts)


def test_embeddings_accepts_single_string(loaded_runtime, monkeypatch) -> None:
    """OpenAI 协议允许 input 直接使用单个字符串。"""

    vector = [0.3] * 1024
    embed_mock = Mock(
        return_value=EmbeddingInferenceResult(vectors=[vector], prompt_tokens=4)
    )
    monkeypatch.setattr(runtime, "embed", embed_mock)

    response = client.post(
        "/v1/embeddings",
        json={"model": "BAAI/bge-m3", "input": "求职助手"},
    )

    assert response.status_code == 200
    assert response.json()["data"][0]["embedding"] == vector
    embed_mock.assert_called_once_with(["求职助手"])


@pytest.mark.parametrize(
    "payload",
    [
        {"model": "BAAI/bge-m3", "input": []},
        {"model": "BAAI/bge-m3", "input": ["有效文本", ""]},
        {"model": "BAAI/bge-m3", "input": ["文本"], "dimensions": 1536},
    ],
)
def test_embeddings_rejects_invalid_input(payload: dict) -> None:
    """空输入、空文本和错误维度必须在推理前失败。"""

    response = client.post("/v1/embeddings", json=payload)

    assert response.status_code == 422


def test_embeddings_rejects_unknown_model() -> None:
    """未知模型名不能静默路由到本地 BGE-M3。"""

    response = client.post(
        "/v1/embeddings",
        json={"model": "unknown/model", "input": ["文本"]},
    )

    assert response.status_code == 404
