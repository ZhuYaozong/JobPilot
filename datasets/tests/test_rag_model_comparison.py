"""RAG 双模型配对分析测试。"""

from __future__ import annotations

from copy import deepcopy

import pytest

from jobpilot_datasets.evaluation.comparison import RagModelComparison
from jobpilot_datasets.models import ExperimentCaseResult


def _record(
    case_index: int,
    variant: str,
    *,
    answer_score: float,
    latency_ms: int,
) -> ExperimentCaseResult:
    return ExperimentCaseResult.model_validate(
        {
            "case_index": case_index,
            "variant": variant,
            "retrieval_strategy": "hybrid",
            "reranker_enabled": True,
            "question": f"问题 {case_index}",
            "reference_answer": f"答案 {case_index}",
            "source_document": f"doc-{case_index}.md",
            "generated_answer": f"{variant} 回答",
            "retrieved_sources": [f"doc-{case_index}.md"],
            "retrieval_metrics": {
                "recall_at_k": 1,
                "hit_at_k": 1,
                "reciprocal_rank": 1,
                "excerpt_recall": 0.8,
            },
            "answer_metrics": {
                "answer_score": answer_score,
                "faithfulness": answer_score,
                "token_f1": answer_score,
                "rouge_l": answer_score,
                "source_support": answer_score,
            },
            "latency_ms": latency_ms,
        },
    )


def test_builds_deterministic_paired_report() -> None:
    records = [
        _record(0, "Base + RAG", answer_score=0.2, latency_ms=100),
        _record(0, "LoRA + RAG", answer_score=0.4, latency_ms=80),
        _record(1, "Base + RAG", answer_score=0.5, latency_ms=120),
        _record(1, "LoRA + RAG", answer_score=0.4, latency_ms=90),
    ]
    analyzer = RagModelComparison(bootstrap_samples=100, seed=7)

    report = analyzer.build(records)
    repeated = analyzer.build(records)

    assert report == repeated
    assert report["paired_count"] == 2
    assert report["retrieval_alignment"] == {"matched": 2, "mismatched": 0}
    score = report["lora_minus_base"]["answer_score"]
    assert score["mean_delta"] == pytest.approx(0.05)
    assert (score["wins"], score["ties"], score["losses"]) == (1, 0, 1)
    assert report["lora_minus_base"]["latency_ms"]["mean_delta"] == -25
    assert report["lora_minus_base"]["latency_ms"]["wins"] == 2
    assert report["variants"]["Base + RAG"]["answer_length_chars_average"] > 0


def test_rejects_different_retrieval_contexts() -> None:
    base = _record(0, "Base + RAG", answer_score=0.2, latency_ms=100)
    lora_payload = deepcopy(
        _record(0, "LoRA + RAG", answer_score=0.4, latency_ms=80).model_dump(),
    )
    lora_payload["retrieved_sources"] = ["another-document.md"]

    with pytest.raises(ValueError, match="检索上下文不一致"):
        RagModelComparison(bootstrap_samples=10).build(
            [base, ExperimentCaseResult.model_validate(lora_payload)],
        )
