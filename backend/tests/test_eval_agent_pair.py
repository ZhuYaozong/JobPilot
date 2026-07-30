"""500 条领域数据经 Agent 配对评测的纯函数测试。"""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

from app.eval.agent_pair_cli import (
    latest_results_by_plan,
    load_source_records,
    record_to_case,
    result_to_record,
    run_model_batch,
    select_records,
)
from app.eval.agent_pair_report import has_duplicate_tool_call, summarize_agent
from app.eval.cases import CaseResult, CaseTrace


def _source_record(index: int, task_type: str) -> dict:
    return {
        "status": "success",
        "plan_id": f"plan-{index}",
        "index": index,
        "task_type": task_type,
        "record_sha256": f"sha-{index}",
        "instruction": f"问题 {index}",
        "input": f"补充 {index}" if index % 2 else "",
        "reference": f"答案 {index}",
    }


def test_load_source_validates_count_and_dataset_sha(tmp_path: Path) -> None:
    source = tmp_path / "source.jsonl"
    rows = [_source_record(0, "A"), _source_record(1, "B")]
    source.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    summary = tmp_path / "summary.json"
    summary.write_text(
        json.dumps({"dataset_sha256": "dataset-sha", "exact_prompt_leakage": {}}),
        encoding="utf-8",
    )
    config_path = tmp_path / "config.json"
    config = {
        "source_results_path": "source.jsonl",
        "source_summary_path": "summary.json",
        "expected_count": 2,
        "dataset_sha256": "dataset-sha",
    }

    records, preflight = load_source_records(config, config_path=config_path)

    assert [record["plan_id"] for record in records] == ["plan-0", "plan-1"]
    assert preflight["unique_plan_ids"] == 2
    assert preflight["source_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()


def test_select_records_balances_task_types() -> None:
    records = [
        _source_record(0, "A"),
        _source_record(1, "A"),
        _source_record(2, "A"),
        _source_record(3, "B"),
        _source_record(4, "B"),
        _source_record(5, "B"),
    ]
    selected = select_records(records, sample_per_task=2, limit=None)
    assert [record["plan_id"] for record in selected] == [
        "plan-0", "plan-1", "plan-3", "plan-4",
    ]


def test_record_to_case_requires_direct_route() -> None:
    case = record_to_case(_source_record(1, "简历优化"))
    assert case.user_text == "问题 1\n补充 1"
    assert [item.type for item in case.assertions] == [
        "agent_run_status", "tool_call_count", "tool_not_called",
    ]
    assert case.assertions[1].params == {"exact": 0}


def test_result_record_preserves_agent_failure_and_tool_trace() -> None:
    source = _source_record(0, "A")
    trace = CaseTrace(
        conversation_id=1,
        agent_run_id=2,
        agent_run_status="succeeded",
        agent_run_error_class=None,
        agent_run_error_detail=None,
        final_text="回答",
        tool_calls=[{
            "tool_name": "list_user_jobs",
            "status": "success",
            "arguments": {},
        }],
    )
    result = CaseResult(
        case=record_to_case(source),
        passed=False,
        duration_ms=1234,
        assertions=[],
        trace=trace,
    )
    row = result_to_record(source, model="jobpilot-base", result=result)
    assert row["status"] == "success"
    assert row["case_passed"] is False
    assert row["prediction"] == "回答"
    assert row["agent"]["tool_sequence"] == ["list_user_jobs"]


def test_agent_summary_detects_duplicate_tool_and_route_leakage() -> None:
    row = {
        "status": "success",
        "case_passed": False,
        "latency_seconds": 2.0,
        "agent": {
            "tool_calls": [
                {"tool_name": "list_user_jobs", "arguments": {"query": "腾讯"}},
                {"tool_name": "list_user_jobs", "arguments": {"query": "腾讯"}},
            ],
        },
    }
    assert has_duplicate_tool_call(row) is True
    summary = summarize_agent([row])
    assert summary["workflow_success_rate"] == 1.0
    assert summary["case_pass_rate"] == 0.0
    assert summary["tool_leakage_rate"] == 1.0
    assert summary["duplicate_tool_rate"] == 1.0


def test_latest_results_uses_last_attempt(tmp_path: Path) -> None:
    path = tmp_path / "results.jsonl"
    path.write_text(
        json.dumps({"plan_id": "p1", "status": "failed"}) + "\n"
        + json.dumps({"plan_id": "p1", "status": "success"}) + "\n",
        encoding="utf-8",
    )
    assert latest_results_by_plan(path)["p1"]["status"] == "success"


def test_run_model_batch_writes_each_completed_record(
    tmp_path: Path,
    monkeypatch,
) -> None:
    active = 0
    max_active = 0

    async def _fake_run_single_case(case, **_kwargs) -> CaseResult:
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.01)
        active -= 1
        return CaseResult(
            case=case,
            passed=True,
            duration_ms=10,
            assertions=[],
            trace=CaseTrace(
                conversation_id=1,
                agent_run_id=1,
                agent_run_status="succeeded",
                agent_run_error_class=None,
                agent_run_error_detail=None,
                final_text="回答",
                tool_calls=[],
            ),
        )

    monkeypatch.setattr(
        "app.eval.agent_pair_cli._run_single_case",
        _fake_run_single_case,
    )
    path = tmp_path / "batch.jsonl"
    asyncio.run(run_model_batch(
        [_source_record(index, "A") for index in range(4)],
        model="jobpilot-base",
        output_path=path,
        excluded_tools=frozenset({"search_knowledge"}),
        timeout_seconds=30,
        concurrency=2,
    ))

    assert len(path.read_text(encoding="utf-8").splitlines()) == 4
    assert max_active == 2
