"""把独立 500 条领域数据通过完整 LangGraph Agent 做 Base/LoRA 配对评测。"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from app.eval.cases import AssertionSpec, CaseResult, EvalCase
from app.eval.runner import _model_override, _run_single_case


REQUIRED_SOURCE_FIELDS = {
    "plan_id",
    "task_type",
    "instruction",
    "reference",
    "record_sha256",
}


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    config_path = Path(args.config).resolve()
    config = _read_json(config_path)
    records, preflight = load_source_records(config, config_path=config_path)
    selected = select_records(
        records,
        sample_per_task=args.sample_per_task,
        limit=args.limit,
    )
    models = args.models or list(config["models"])
    output_root = _resolve_config_path(config_path, config["output_dir"])
    run_dir = output_root / args.run_name
    run_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "run_name": args.run_name,
        "models": models,
        "selected_count": len(selected),
        "selected_plan_ids": [str(record["plan_id"]) for record in selected],
        "task_counts": _task_counts(selected),
        "excluded_tools": list(config.get("excluded_tools") or []),
        "timeout_seconds": float(config.get("timeout_seconds", 120)),
        "concurrency": int(config.get("concurrency", 1)),
        "source_path": str(preflight["source_path"]),
        "source_sha256": preflight["source_sha256"],
        "dataset_sha256": preflight.get("dataset_sha256"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_json(run_dir / "preflight.json", preflight)
    _write_json(run_dir / "run_metadata.json", metadata)

    for model in models:
        output_path = run_dir / f"{safe_model_name(model)}.jsonl"
        finished = latest_results_by_plan(output_path)
        pending = [
            record for record in selected
            if (
                args.retry_failed
                and finished.get(str(record["plan_id"]), {}).get("status") != "success"
            ) or (
                not args.retry_failed
                and str(record["plan_id"]) not in finished
            )
        ]
        print(f"[{model}] 已完成 {len(selected) - len(pending)}/{len(selected)}")
        with _model_override(model):
            asyncio.run(run_model_batch(
                pending,
                model=model,
                output_path=output_path,
                excluded_tools=frozenset(config.get("excluded_tools") or []),
                timeout_seconds=float(config.get("timeout_seconds", 120)),
                concurrency=int(config.get("concurrency", 1)),
            ))

    print(f"运行完成: {run_dir}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Agent 配对评测 JSON 配置")
    parser.add_argument("--run-name", default="full", help="输出子目录名")
    parser.add_argument("--limit", type=int, default=None, help="只取前 N 条")
    parser.add_argument(
        "--sample-per-task",
        type=int,
        default=None,
        help="每个 task_type 按原顺序抽取 N 条",
    )
    parser.add_argument(
        "--model",
        action="append",
        dest="models",
        help="覆盖配置模型，可重复指定",
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="保留成功结果，仅重跑失败记录",
    )
    return parser


async def run_model_batch(
    records: list[dict[str, Any]],
    *,
    model: str,
    output_path: Path,
    excluded_tools: frozenset[str],
    timeout_seconds: float,
    concurrency: int,
) -> None:
    """同一模型内有限并发执行，完成事件由主协程串行写入 JSONL。"""
    if concurrency <= 0:
        raise ValueError("concurrency 必须大于 0")
    semaphore = asyncio.Semaphore(concurrency)

    async def _run(record: dict[str, Any]) -> tuple[dict[str, Any], CaseResult]:
        async with semaphore:
            result = await _run_single_case(
                record_to_case(record),
                live=True,
                enable_judge=False,
                excluded_tools=excluded_tools,
                timeout_seconds=timeout_seconds,
            )
            return record, result

    tasks = [asyncio.create_task(_run(record)) for record in records]
    for position, task in enumerate(asyncio.as_completed(tasks), start=1):
        record, result = await task
        row = result_to_record(record, model=model, result=result)
        append_jsonl(output_path, row)
        status = "OK" if row["status"] == "success" else "FAIL"
        tools = ",".join(row["agent"]["tool_sequence"]) or "-"
        print(
            f"[{model}] {position}/{len(records)} {record['plan_id']} "
            f"[{status}] {row['latency_seconds']:.2f}s tools={tools}",
            flush=True,
        )


def load_source_records(
    config: dict[str, Any],
    *,
    config_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """读取之前单轮评测的冻结输入，并验证数量、唯一性和数据集哈希。"""
    source_path = _resolve_config_path(config_path, config["source_results_path"])
    source_summary_path = _resolve_config_path(
        config_path,
        config["source_summary_path"],
    )
    source_summary = _read_json(source_summary_path)
    raw_records = _read_jsonl(source_path)
    selected: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(raw_records):
        missing = REQUIRED_SOURCE_FIELDS - set(record)
        if missing:
            raise ValueError(f"源记录 {index} 缺少字段: {sorted(missing)}")
        plan_id = str(record["plan_id"])
        if plan_id in selected:
            raise ValueError(f"源记录 plan_id 重复: {plan_id}")
        selected[plan_id] = {
            "plan_id": plan_id,
            "index": int(record.get("index", index)),
            "task_type": str(record["task_type"]),
            "record_sha256": str(record["record_sha256"]),
            "instruction": str(record["instruction"]).strip(),
            "input": str(record.get("input") or "").strip(),
            "reference": str(record["reference"]).strip(),
        }
    records = sorted(selected.values(), key=lambda item: item["index"])
    expected_count = int(config.get("expected_count", 500))
    if len(records) != expected_count:
        raise ValueError(f"源记录应为 {expected_count} 条，实际 {len(records)} 条")

    expected_dataset_sha = str(config["dataset_sha256"])
    actual_dataset_sha = str(source_summary.get("dataset_sha256") or "")
    if actual_dataset_sha != expected_dataset_sha:
        raise ValueError(
            f"数据集 SHA256 不一致: {actual_dataset_sha} != {expected_dataset_sha}",
        )
    return records, {
        "status": "passed",
        "source_path": str(source_path),
        "source_sha256": _sha256_file(source_path),
        "source_record_count": len(records),
        "unique_plan_ids": len(selected),
        "dataset_sha256": actual_dataset_sha,
        "exact_prompt_leakage": source_summary.get("exact_prompt_leakage") or {},
        "task_counts": _task_counts(records),
    }


def select_records(
    records: list[dict[str, Any]],
    *,
    sample_per_task: int | None,
    limit: int | None,
) -> list[dict[str, Any]]:
    """按任务类型做稳定抽样；未指定时保持原始 500 条顺序。"""
    selected = records
    if sample_per_task is not None:
        if sample_per_task <= 0:
            raise ValueError("sample_per_task 必须大于 0")
        grouped_count: dict[str, int] = defaultdict(int)
        selected = []
        for record in records:
            task_type = str(record["task_type"])
            if grouped_count[task_type] >= sample_per_task:
                continue
            selected.append(record)
            grouped_count[task_type] += 1
    if limit is not None:
        if limit <= 0:
            raise ValueError("limit 必须大于 0")
        selected = selected[:limit]
    return selected


def record_to_case(record: dict[str, Any]) -> EvalCase:
    """把一条领域问答转换成完整 Agent turn；正确路线应为无工具直答。"""
    instruction = str(record["instruction"]).strip()
    extra_input = str(record.get("input") or "").strip()
    user_text = instruction if not extra_input else f"{instruction}\n{extra_input}"
    return EvalCase(
        name=str(record["plan_id"]),
        description=f"{record['task_type']}领域问答，经完整 Agent 决策链执行",
        user_text=user_text,
        assertions=[
            AssertionSpec(type="agent_run_status", params={"status": "succeeded"}),
            AssertionSpec(type="tool_call_count", params={"exact": 0}),
            AssertionSpec(type="tool_not_called", params={"tool": "search_knowledge"}),
        ],
    )


def result_to_record(
    source: dict[str, Any],
    *,
    model: str,
    result: CaseResult,
) -> dict[str, Any]:
    """把 runner 结果摊平成可流式追加、可恢复的 JSONL 记录。"""
    trace = result.trace
    tool_calls = trace.tool_calls if trace else []
    prediction = trace.final_text if trace and trace.final_text else ""
    workflow_succeeded = bool(
        trace and trace.agent_run_status == "succeeded" and prediction,
    )
    return {
        "status": "success" if workflow_succeeded else "failed",
        "plan_id": str(source["plan_id"]),
        "index": int(source["index"]),
        "task_type": str(source["task_type"]),
        "record_sha256": str(source["record_sha256"]),
        "prompt_sha256": _prompt_sha256(source),
        "model": model,
        "instruction": str(source["instruction"]),
        "input": str(source.get("input") or ""),
        "reference": str(source["reference"]),
        "prediction": prediction,
        "latency_seconds": round(result.duration_ms / 1000, 4),
        "case_passed": bool(result.passed),
        "framework_error": result.error,
        "failed_assertions": [
            assertion.spec.type
            for assertion in result.assertions
            if not assertion.passed
        ],
        "agent": {
            "run_status": trace.agent_run_status if trace else None,
            "error_class": trace.agent_run_error_class if trace else None,
            "error_detail": trace.agent_run_error_detail if trace else None,
            "tool_sequence": [call.get("tool_name") for call in tool_calls],
            "tool_calls": tool_calls,
        },
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }


def latest_results_by_plan(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    return {
        str(record["plan_id"]): record
        for record in _read_jsonl(path)
        if record.get("plan_id")
    }


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as file:
        json.dump(value, file, ensure_ascii=False)
        file.write("\n")
        file.flush()


def safe_model_name(model: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", model)


def _task_counts(records: Iterable[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for record in records:
        counts[str(record["task_type"])] += 1
    return dict(sorted(counts.items()))


def _prompt_sha256(record: dict[str, Any]) -> str:
    prompt = str(record["instruction"]).strip()
    extra_input = str(record.get("input") or "").strip()
    if extra_input:
        prompt = f"{prompt}\n{extra_input}"
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_config_path(config_path: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    return path.resolve() if path.is_absolute() else (config_path.parent / path).resolve()


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number} JSON 无效") from exc
    return records


def _write_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())
