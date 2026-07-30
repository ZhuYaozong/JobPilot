"""实验矩阵 Profile 测试。"""

from jobpilot_datasets.evaluation.profiles import apply_experiment_profile


def test_retrieval_benchmark_profile_restores_four_strategies(test_config) -> None:
    profiled = apply_experiment_profile(test_config, "retrieval-benchmark")

    assert [item.name for item in profiled.experiments.variants] == [
        "Vector RAG",
        "BM25 RAG",
        "Hybrid RAG",
        "Hybrid + Rerank",
    ]
    assert [
        item.resolved_strategy(profiled.experiments.retriever.kind)
        for item in profiled.experiments.variants
    ] == ["vector", "bm25", "hybrid", "hybrid"]
    assert profiled.experiments.variants[-1].reranker_enabled is True
    assert [item.name for item in test_config.experiments.variants] == [
        "Base + RAG",
        "LoRA + RAG",
    ]
