from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from conftest import DeterministicEmbeddingProvider, PassthroughReranker
from jobpilot_datasets.evaluation import runner as runner_module
from jobpilot_datasets.evaluation.runner import ExperimentRunner
from jobpilot_datasets.evaluation.sweep import RetrievalSweepRunner
from jobpilot_datasets.io_utils import atomic_write_jsonl, atomic_write_text
from jobpilot_datasets.models import RagEvalItem


def _prepare_rag_fixture(test_config) -> list[RagEvalItem]:
    documents = {
        "rag/documents/a.md": "# 向量检索\n\n向量检索使用语义嵌入召回相关内容。",
        "rag/documents/b.md": "# BM25 检索\n\nBM25 使用关键词频率和逆文档频率排序。",
    }
    for relative_path, content in documents.items():
        atomic_write_text(test_config.resolve_path(Path(relative_path)), content)

    cases = [
        RagEvalItem(
            question="向量检索依靠什么召回？",
            answer="向量检索依靠语义嵌入。",
            source_document="rag/documents/a.md",
            supporting_excerpt="向量检索使用语义嵌入召回相关内容。",
        ),
        RagEvalItem(
            question="语义嵌入用于哪种检索？",
            answer="用于向量检索。",
            source_document="rag/documents/a.md",
            supporting_excerpt="向量检索使用语义嵌入召回相关内容。",
        ),
        RagEvalItem(
            question="BM25 根据什么进行排序？",
            answer="根据词频和逆文档频率排序。",
            source_document="rag/documents/b.md",
            supporting_excerpt="BM25 使用关键词频率和逆文档频率排序。",
        ),
        RagEvalItem(
            question="哪种检索使用关键词频率？",
            answer="BM25 检索。",
            source_document="rag/documents/b.md",
            supporting_excerpt="BM25 使用关键词频率和逆文档频率排序。",
        ),
    ]
    evaluation_path = test_config.resolve_path(
        test_config.experiments.evaluation_file,
    )
    atomic_write_jsonl(
        evaluation_path,
        [case.model_dump(mode="json") for case in cases],
    )
    return cases


@pytest.mark.asyncio
async def test_case_subset_still_loads_complete_corpus(test_config) -> None:
    cases = _prepare_rag_fixture(test_config)
    captured_sources: list[str] = []
    original_load_chunks = runner_module.load_chunks

    def capture_load_chunks(
        output_root: Path,
        source_documents: list[str],
        *,
        chunk_size: int,
        chunk_overlap: int,
    ):
        captured_sources.extend(source_documents)
        return original_load_chunks(
            output_root,
            source_documents,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    with patch.object(runner_module, "load_chunks", side_effect=capture_load_chunks):
        report = await ExperimentRunner(
            test_config,
            embedding_provider_override=DeterministicEmbeddingProvider(),
            reranker_provider_override=PassthroughReranker(),
            report_subdir="tests/full-corpus",
        ).run(case_indices=[0], retrieval_only=True)

    assert report.evaluation_count == 1
    assert set(captured_sources) == {
        case.source_document for case in cases
    }


@pytest.mark.asyncio
async def test_retrieval_sweep_uses_disjoint_stratified_sets(test_config) -> None:
    cases = _prepare_rag_fixture(test_config)

    def runner_factory(config, report_subdir: Path) -> ExperimentRunner:
        return ExperimentRunner(
            config,
            embedding_provider_override=DeterministicEmbeddingProvider(),
            reranker_provider_override=PassthroughReranker(),
            report_subdir=report_subdir,
        )

    report = await RetrievalSweepRunner(
        test_config,
        runner_factory=runner_factory,
        progress=lambda _message: None,
    ).run()

    tuning = set(report["tuning_case_indices"])
    validation = set(report["validation_case_indices"])
    assert len(tuning) == 2
    assert len(validation) == 2
    assert tuning.isdisjoint(validation)
    assert tuning | validation == set(range(len(cases)))
    assert report["corpus_document_count"] == 2
    assert len(report["tuning_results"]) == 14
    assert 3 <= len(report["validation_results"]) <= 4
    assert report["winner"]["slug"]
    assert report["baseline_validation"]["slug"] == (
        RetrievalSweepRunner.BASELINE.slug
    )

    output_dir = (
        test_config.resolve_path(test_config.paths.reports_dir)
        / "retrieval-sweep"
    )
    assert (output_dir / "retrieval_sweep_report.json").exists()
    assert (output_dir / "retrieval_sweep_report.md").exists()
