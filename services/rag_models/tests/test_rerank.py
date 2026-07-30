"""Reranker API 与稳定排序测试。"""

from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from services.rag_models.app import app, runtime
from services.rag_models.config import RagModelSettings
from services.rag_models.model_runtime import (
    ModelRuntime,
    RerankInferenceResult,
    RerankScore,
)


client = TestClient(app)


@pytest.fixture
def loaded_runtime(monkeypatch):
    """用轻量假对象模拟两个模型已经完成加载。"""

    monkeypatch.setattr(runtime, "_embedder", object())
    monkeypatch.setattr(runtime, "_reranker", object())


def test_rerank_returns_503_when_models_are_not_ready() -> None:
    """模型未就绪时不能接受精排请求。"""

    response = client.post(
        "/v1/rerank",
        json={
            "model": "BAAI/bge-reranker-v2-m3",
            "query": "Python 后端",
            "documents": ["FastAPI 项目"],
            "top_n": 1,
        },
    )

    assert response.status_code == 503


def test_rerank_api_preserves_original_indices(loaded_runtime, monkeypatch) -> None:
    """API 返回排序后的分数，但 index 必须指向原始候选。"""

    rerank_mock = Mock(
        return_value=RerankInferenceResult(
            results=[
                RerankScore(index=1, relevance_score=0.9),
                RerankScore(index=0, relevance_score=0.5),
            ]
        )
    )
    monkeypatch.setattr(runtime, "rerank", rerank_mock)

    documents = ["Python 后端", "FastAPI RAG 项目", "天气预报"]
    response = client.post(
        "/v1/rerank",
        json={
            "model": "BAAI/bge-reranker-v2-m3",
            "query": "后端项目经验",
            "documents": documents,
            "top_n": 2,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["model"] == "BAAI/bge-reranker-v2-m3"
    assert payload["results"] == [
        {"index": 1, "relevance_score": 0.9},
        {"index": 0, "relevance_score": 0.5},
    ]
    rerank_mock.assert_called_once_with("后端项目经验", documents, 2)


def test_runtime_rerank_uses_stable_score_order() -> None:
    """相同分数必须按原索引排序，避免候选映射抖动。"""

    fake_reranker = Mock()
    fake_reranker.compute_score.return_value = [0.5, 0.9, 0.5]
    test_runtime = ModelRuntime(
        RagModelSettings(device="cpu", load_models_on_startup=False)
    )
    test_runtime._embedder = object()
    test_runtime._reranker = fake_reranker

    result = test_runtime.rerank(
        "后端开发",
        ["候选一", "候选二", "候选三"],
        top_n=3,
    )

    assert [item.index for item in result.results] == [1, 0, 2]
    assert [item.relevance_score for item in result.results] == pytest.approx(
        [0.9, 0.5, 0.5]
    )


def test_runtime_rerank_accepts_single_scalar_score() -> None:
    """FlagEmbedding 对单候选返回标量时也应统一为列表结果。"""

    fake_reranker = Mock()
    fake_reranker.compute_score.return_value = 0.75
    test_runtime = ModelRuntime(
        RagModelSettings(device="cpu", load_models_on_startup=False)
    )
    test_runtime._embedder = object()
    test_runtime._reranker = fake_reranker

    result = test_runtime.rerank("查询", ["唯一候选"], top_n=1)

    assert result.results[0].index == 0
    assert result.results[0].relevance_score == pytest.approx(0.75)


@pytest.mark.parametrize(
    "payload",
    [
        {
            "model": "BAAI/bge-reranker-v2-m3",
            "query": "",
            "documents": ["候选"],
            "top_n": 1,
        },
        {
            "model": "BAAI/bge-reranker-v2-m3",
            "query": "查询",
            "documents": [],
            "top_n": 1,
        },
        {
            "model": "BAAI/bge-reranker-v2-m3",
            "query": "查询",
            "documents": ["候选", ""],
            "top_n": 1,
        },
        {
            "model": "BAAI/bge-reranker-v2-m3",
            "query": "查询",
            "documents": ["候选"],
            "top_n": 2,
        },
    ],
)
def test_rerank_rejects_invalid_input(payload: dict) -> None:
    """无效查询、候选和 Top-N 必须在推理前失败。"""

    response = client.post("/v1/rerank", json=payload)

    assert response.status_code == 422


def test_rerank_rejects_unknown_model() -> None:
    """未知模型名不能静默路由到本地 Reranker。"""

    response = client.post(
        "/v1/rerank",
        json={
            "model": "unknown/reranker",
            "query": "查询",
            "documents": ["候选"],
            "top_n": 1,
        },
    )

    assert response.status_code == 404
