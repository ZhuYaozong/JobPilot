"""RAG 配置开关与装配测试。"""

from app.core.config import Settings
from app.rag.bm25 import BM25Retriever
from app.rag.factory import build_retrieval_service
from app.rag.hybrid import HybridRetriever
from app.rag.reranker import HttpReranker
from app.rag.vector import VectorRetriever


def _settings(**overrides) -> Settings:  # noqa: ANN003
    return Settings(_env_file=None, **overrides)


def test_factory_defaults_to_hybrid_with_reranker() -> None:
    service = build_retrieval_service(app_settings=_settings())

    assert isinstance(service.retriever, HybridRetriever)
    assert isinstance(service.reranker, HttpReranker)


def test_factory_supports_all_retrieval_strategies() -> None:
    vector = build_retrieval_service(app_settings=_settings(rag_strategy="vector"))
    bm25 = build_retrieval_service(app_settings=_settings(rag_strategy="bm25"))
    hybrid = build_retrieval_service(app_settings=_settings(rag_strategy="hybrid"))

    assert isinstance(vector.retriever, VectorRetriever)
    assert isinstance(bm25.retriever, BM25Retriever)
    assert isinstance(hybrid.retriever, HybridRetriever)


def test_factory_only_builds_reranker_when_enabled() -> None:
    disabled = build_retrieval_service(
        app_settings=_settings(rag_reranker_enabled=False),
    )
    enabled = build_retrieval_service(
        app_settings=_settings(
            rag_reranker_enabled=True,
            reranker_base_url="https://rerank.example/v1",
            reranker_model_name="reranker",
        ),
    )

    assert disabled.reranker is None
    assert isinstance(enabled.reranker, HttpReranker)
