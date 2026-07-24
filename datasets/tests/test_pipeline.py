from pathlib import Path

import pytest

from conftest import DeterministicProvider
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
        "先校验请求并设置超时与指数退避重试，持续失败则降级；同时记录"
        "P95延迟、错误分类和请求标识，以支持告警、回放和灰度回滚。",
    )
    experiment = await ExperimentRunner(
        test_config,
        provider_overrides={
            "base": base_provider,
            "lora": lora_provider,
        },
    ).run(limit=2)
    assert [item.name for item in experiment.variants] == [
        "Base",
        "Base+RAG",
        "LoRA",
        "LoRA+RAG",
    ]
    assert all(item.case_count == 2 for item in experiment.variants)
    report_path = (
        test_config.resolve_path(test_config.paths.reports_dir)
        / "experiments"
        / "experiment_report.md"
    )
    assert report_path.exists()
