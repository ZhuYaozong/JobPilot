"""可复现的实验矩阵 Profile。"""

from __future__ import annotations

from jobpilot_datasets.config import AppConfig, ExperimentVariantConfig


def apply_experiment_profile(config: AppConfig, profile: str) -> AppConfig:
    """在不复制完整 YAML 的前提下切换实验矩阵。"""
    if profile == "configured":
        return config
    if profile != "retrieval-benchmark":
        raise ValueError(f"未知实验 Profile: {profile}")

    variants = [
        ExperimentVariantConfig(
            name="Vector RAG",
            provider="base",
            use_rag=True,
            retrieval_strategy="vector",
        ),
        ExperimentVariantConfig(
            name="BM25 RAG",
            provider="base",
            use_rag=True,
            retrieval_strategy="bm25",
        ),
        ExperimentVariantConfig(
            name="Hybrid RAG",
            provider="base",
            use_rag=True,
            retrieval_strategy="hybrid",
        ),
        ExperimentVariantConfig(
            name="Hybrid + Rerank",
            provider="base",
            use_rag=True,
            retrieval_strategy="hybrid",
            reranker_enabled=True,
        ),
    ]
    experiments = config.experiments.model_copy(update={"variants": variants})
    return config.model_copy(update={"experiments": experiments})
