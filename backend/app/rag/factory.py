"""依据配置装配生产 Retriever 与 Reranker。"""

from __future__ import annotations

from collections.abc import Callable

from app.core.config import Settings, settings
from app.llm.embedding_client import EmbeddingClient
from app.rag.bm25 import BM25Retriever
from app.rag.hybrid import HybridRetriever
from app.rag.reranker import HttpReranker
from app.rag.service import RetrievalService
from app.rag.vector import VectorRetriever


def build_retrieval_service(
    *,
    app_settings: Settings = settings,
    embedding_client_factory: Callable[[], EmbeddingClient] = EmbeddingClient,
) -> RetrievalService:
    """集中装配依赖，让 Agent 工具只依赖稳定服务接口。"""
    vector = VectorRetriever(embedding_client_factory)
    bm25 = BM25Retriever(k1=app_settings.rag_bm25_k1, b=app_settings.rag_bm25_b)
    if app_settings.rag_strategy == "vector":
        retriever = vector
    elif app_settings.rag_strategy == "bm25":
        retriever = bm25
    else:
        retriever = HybridRetriever(
            vector,
            bm25,
            rrf_k=app_settings.rag_hybrid_rrf_k,
            vector_weight=app_settings.rag_vector_weight,
            bm25_weight=app_settings.rag_bm25_weight,
            vector_fail_open=app_settings.rag_hybrid_vector_fail_open,
        )

    reranker = None
    if app_settings.rag_reranker_enabled:
        reranker = HttpReranker(
            base_url=app_settings.reranker_base_url,
            api_key=app_settings.reranker_api_key,
            model_name=app_settings.reranker_model_name,
            timeout_seconds=app_settings.reranker_timeout_seconds,
        )
    return RetrievalService(
        retriever,
        candidate_multiplier=app_settings.rag_candidate_multiplier,
        reranker=reranker,
        reranker_fail_open=app_settings.rag_reranker_fail_open,
    )
