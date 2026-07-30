from pathlib import Path

import pytest

from conftest import (
    DeterministicEmbeddingProvider,
    DeterministicProvider,
    PassthroughReranker,
)
from jobpilot_datasets.evaluation.runner import ExperimentRunner
from jobpilot_datasets.pipeline import DatasetPipeline
from jobpilot_datasets.quality import QualityInspector


@pytest.mark.asyncio
async def test_full_pipeline_resume_quality_and_experiment(test_config) -> None:
    first_provider = DeterministicProvider()
    partial = DatasetPipeline(
        test_config,
        first_provider,
        resume=False,
    )
    partial_result = await partial.generate_sft(limit=1)
    await partial.close()
    assert not partial_result.completed

    provider = DeterministicProvider()
    pipeline = DatasetPipeline(
        test_config,
        provider,
        resume=True,
    )
    sft_result = await pipeline.generate_sft()
    lora_evaluation_result = await pipeline.generate_lora_evaluation()
    document_result = await pipeline.generate_rag_documents()
    evaluation_result = await pipeline.generate_rag_evaluation()
    await pipeline.close()

    assert sft_result.completed
    assert lora_evaluation_result.completed
    assert document_result.completed
    assert evaluation_result.completed
    assert (test_config.resolve_path(test_config.paths.lora_dir) / "train.jsonl").exists()
    assert (
        test_config.resolve_path(test_config.paths.evaluation_dir)
        / "rag_test.jsonl"
    ).exists()
    assert (
        test_config.resolve_path(test_config.paths.evaluation_dir)
        / "lora_test.jsonl"
    ).exists()

    quality_report = QualityInspector(test_config).run()
    assert quality_report.passed, [
        issue.model_dump() for issue in quality_report.issues
    ]

    base_provider = DeterministicProvider(
        "服务应设置有限重试、监控错误率并在失败时降级和回滚。",
    )
    lora_provider = DeterministicProvider(
        "服务应设置有限重试、监控错误率并在失败时降级和回滚。",
    )
    experiment = await ExperimentRunner(
        test_config,
        provider_overrides={
            "base": base_provider,
            "lora": lora_provider,
        },
        embedding_provider_override=DeterministicEmbeddingProvider(),
        reranker_provider_override=PassthroughReranker(),
    ).run(limit=2)
    assert [item.name for item in experiment.variants] == [
        "Base + RAG",
        "LoRA + RAG",
    ]
    assert all(item.case_count == 2 for item in experiment.variants)
    assert experiment.mode == "end_to_end"
    assert all(
        item.answer_metrics is not None
        and "answer_score" in item.answer_metrics
        for item in experiment.variants
    )
    assert all(
        item.answer_metrics is not None
        and "faithfulness" in item.answer_metrics
        for item in experiment.variants
    )
    assert all(
        item.retrieval_metrics is not None
        and "recall_at_k" in item.retrieval_metrics
        and "mrr" in item.retrieval_metrics
        and item.retrieval_strategy == "hybrid"
        and item.reranker_enabled
        for item in experiment.variants
    )
    report_path = (
        test_config.resolve_path(test_config.paths.reports_dir)
        / "experiments"
        / "experiment_report.md"
    )
    assert report_path.exists()

    unused_provider = DeterministicProvider()
    retrieval_experiment = await ExperimentRunner(
        test_config,
        provider_overrides={"base": unused_provider},
        embedding_provider_override=DeterministicEmbeddingProvider(),
        reranker_provider_override=PassthroughReranker(),
    ).run(limit=2, retrieval_only=True)
    assert retrieval_experiment.mode == "retrieval_only"
    assert all(
        item.answer_metrics is None
        and item.judge_metrics is None
        and item.latency_ms_p95 >= 0
        for item in retrieval_experiment.variants
    )
    assert unused_provider.requests == []
