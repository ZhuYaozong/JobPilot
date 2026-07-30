"""Agent + Hybrid RAG 配对评测的纯函数与调度测试。"""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

import pytest

from app.core.config import settings
from app.eval.agent_rag_fixture import load_document_specs
from app.eval.agent_rag_pair_cli import (
    extract_retrieved_hits,
    load_rag_records,
    run_model_batch,
    search_only_catalog,
    should_run_case,
    strict_rag_settings,
)
from app.eval.agent_rag_pair_report import (
    bootstrap_mean_ci,
    paired_comparison,
    score_record,
    summarize_agent,
    tokenize,
)
from app.eval.agent_rag_fixture import FixtureSnapshot


def _write_dataset(tmp_path: Path) -> tuple[Path, Path, list[dict]]:
    dataset_root = tmp_path / "datasets"
    documents = dataset_root / "rag" / "documents"
    evaluation = dataset_root / "evaluation"
    documents.mkdir(parents=True)
    evaluation.mkdir(parents=True)
    rows = []
    for index in range(2):
        source = f"rag/documents/doc-{index}.md"
        (documents / f"doc-{index}.md").write_text(
            f"# 文档{index}\n\n证据内容{index}。\n",
            encoding="utf-8",
        )
        rows.append({
            "question": f"问题{index}",
            "answer": f"答案{index}",
            "source_document": source,
            "supporting_excerpt": f"证据内容{index}",
        })
    evaluation_path = evaluation / "rag_test.jsonl"
    evaluation_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    return dataset_root, evaluation_path, rows


def _config(tmp_path: Path, evaluation_path: Path) -> dict:
    return {
        "dataset_root": str(tmp_path / "datasets"),
        "documents_dir": str(tmp_path / "datasets" / "rag" / "documents"),
        "evaluation_path": str(evaluation_path),
        "expected_count": 2,
        "expected_document_count": 2,
        "dataset_sha256": hashlib.sha256(evaluation_path.read_bytes()).hexdigest(),
    }


def _record(*, model: str = "base", hit: bool = True) -> dict:
    source = "rag/documents/doc-0.md"
    hits = [{
        "document_title": source if hit else "rag/documents/other.md",
        "content": "证据内容0",
    }]
    return {
        "status": "success",
        "case_id": "rag-0000",
        "model": model,
        "question": "问题0",
        "reference_answer": "答案0",
        "source_document": source,
        "supporting_excerpt": "证据内容0",
        "prediction": "答案0",
        "latency_seconds": 2.0,
        "case_passed": True,
        "framework_error": None,
        "agent": {
            "tool_calls": [{
                "tool_name": "search_knowledge",
                "status": "success",
                "arguments": {"knowledge_base_id": 7},
                "result": {"ok": True, "data": {"hits": hits}},
                "latency_ms": 100,
            }],
        },
        "rag": {
            "search_call_count": 1,
            "successful_search_call_count": 1,
            "correct_knowledge_base_call_count": 1,
            "direct_route": False,
            "retrieved_hits": hits,
        },
    }


def test_load_records_and_documents_validate_frozen_sources(tmp_path: Path) -> None:
    _dataset_root, evaluation_path, _rows = _write_dataset(tmp_path)
    config = _config(tmp_path, evaluation_path)
    config_path = tmp_path / "config.json"

    specs = load_document_specs(config, config_path=config_path)
    records, preflight = load_rag_records(config, config_path=config_path)

    assert [spec.source_document for spec in specs] == [
        "rag/documents/doc-0.md", "rag/documents/doc-1.md",
    ]
    assert [record["case_id"] for record in records] == ["rag-0000", "rag-0001"]
    assert preflight["record_count"] == 2
    assert preflight["unique_source_documents"] == 2


def test_load_records_rejects_dataset_hash_drift(tmp_path: Path) -> None:
    _dataset_root, evaluation_path, _rows = _write_dataset(tmp_path)
    config = _config(tmp_path, evaluation_path)
    config["dataset_sha256"] = "0" * 64

    with pytest.raises(ValueError, match="SHA256"):
        load_rag_records(config, config_path=tmp_path / "config.json")


def test_search_catalog_only_exposes_rag_tool() -> None:
    catalog = search_only_catalog()
    assert [descriptor.name for descriptor in catalog.descriptors] == [
        "search_knowledge",
    ]


def test_extract_hits_and_score_record() -> None:
    row = _record()
    calls = row["agent"]["tool_calls"]
    hits = extract_retrieved_hits(calls)
    scores = score_record(row)

    assert hits[0]["document_title"] == row["source_document"]
    assert scores["retrieval"]["recall_at_5"] == 1.0
    assert scores["retrieval"]["mrr"] == 1.0
    assert scores["answer"]["answer_score"] == 1.0


def test_extract_hits_supports_database_flattened_result() -> None:
    call = {
        "tool_name": "search_knowledge",
        "status": "success",
        "result": {"hits": [{"document_title": "doc.md", "content": "证据"}]},
    }

    assert extract_retrieved_hits([call]) == [
        {"document_title": "doc.md", "content": "证据"},
    ]


def test_agent_summary_separates_route_and_workflow_success() -> None:
    direct = _record()
    direct["case_passed"] = False
    direct["agent"]["tool_calls"] = []
    direct["rag"].update({
        "search_call_count": 0,
        "successful_search_call_count": 0,
        "correct_knowledge_base_call_count": 0,
        "direct_route": True,
        "retrieved_hits": [],
    })

    summary = summarize_agent([direct])

    assert summary["workflow_success_rate"] == 1.0
    assert summary["rag_route_pass_rate"] == 0.0
    assert summary["direct_route_rate"] == 1.0


def test_paired_comparison_reports_lora_win_and_source_split() -> None:
    base = _record(model="base", hit=False)
    lora = _record(model="lora", hit=True)
    lora["prediction"] = "答案0"
    base["prediction"] = "完全错误"
    results = {"base": {"rag-0000": base}, "lora": {"rag-0000": lora}}
    metrics = {
        model: {case_id: score_record(row) for case_id, row in values.items()}
        for model, values in results.items()
    }

    paired = paired_comparison(
        results,
        metrics,
        case_ids=["rag-0000"],
        models=["base", "lora"],
        seed=42,
    )

    assert paired["lora_win_count"] == 1
    assert paired["source_hit_pairs"]["lora_only"] == 1


def test_strict_rag_settings_restores_fail_open_flags(monkeypatch) -> None:
    monkeypatch.setattr(settings, "rag_strategy", "hybrid")
    monkeypatch.setattr(settings, "rag_reranker_enabled", True)
    monkeypatch.setattr(settings, "rag_hybrid_vector_fail_open", True)
    monkeypatch.setattr(settings, "rag_reranker_fail_open", True)

    with strict_rag_settings():
        assert settings.rag_hybrid_vector_fail_open is False
        assert settings.rag_reranker_fail_open is False

    assert settings.rag_hybrid_vector_fail_open is True
    assert settings.rag_reranker_fail_open is True


def test_run_model_batch_appends_completed_rows(tmp_path: Path, monkeypatch) -> None:
    async def _fake_case(source, **kwargs):
        await asyncio.sleep(0)
        row = _record(model=kwargs["model"])
        row["case_id"] = source["case_id"]
        row["index"] = source["index"]
        return row

    monkeypatch.setattr(
        "app.eval.agent_rag_pair_cli.run_agent_rag_case",
        _fake_case,
    )
    fixture = FixtureSnapshot(
        user_id=1,
        username="test",
        knowledge_base_id=7,
        knowledge_base_name="kb",
        document_count=2,
        chunk_count=2,
        ready_document_count=2,
        embedding_dimensions=1024,
        document_set_sha256="sha",
    )
    output = tmp_path / "results.jsonl"
    rows = [
        {"case_id": f"rag-{index:04d}", "index": index}
        for index in range(3)
    ]

    asyncio.run(run_model_batch(
        rows,
        model="base",
        fixture=fixture,
        output_path=output,
        timeout_seconds=30,
        concurrency=2,
    ))

    assert len(output.read_text(encoding="utf-8").splitlines()) == 3


def test_tokenizer_and_bootstrap_are_deterministic() -> None:
    assert "混合" in tokenize("Hybrid混合检索")
    assert bootstrap_mean_ci([0.1, 0.2], seed=42) == bootstrap_mean_ci(
        [0.1, 0.2], seed=42,
    )


def test_retry_filter_only_selects_requested_infrastructure_error() -> None:
    unavailable = {"status": "failed", "agent": {"error_class": "llm_unavailable"}}
    protocol = {"status": "failed", "agent": {"error_class": "decide_repair_failed"}}
    requested = frozenset({"llm_unavailable"})

    assert should_run_case(
        unavailable, retry_failed=True, retry_error_classes=requested,
    ) is True
    assert should_run_case(
        protocol, retry_failed=True, retry_error_classes=requested,
    ) is False
    assert should_run_case(
        None, retry_failed=True, retry_error_classes=requested,
    ) is True
