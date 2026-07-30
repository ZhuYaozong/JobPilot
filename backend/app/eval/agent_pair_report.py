"""汇总 500 条 Base/LoRA Agent 配对结果和原单轮结果的差异。"""

from __future__ import annotations

import argparse
import collections
import json
import math
import random
import re
import statistics
from pathlib import Path
from typing import Any, Iterable

from app.eval.agent_pair_cli import (
    _read_json,
    _read_jsonl,
    _resolve_config_path,
    _write_json,
    safe_model_name,
)


SPACE_PATTERN = re.compile(r"\s+")
NUMBER_PATTERN = re.compile(
    r"(?P<number>\d+(?:\.\d+)?)\s*"
    r"(?P<unit>%|％|ms|毫秒|s|秒|分钟|小时|天|万|亿|人|次|倍|GB|MB|KB|QPS)?",
    re.IGNORECASE,
)
SPECULATIVE_MARKERS = (
    "估算", "估计", "假设为", "假定为", "可以写成", "可写为",
    "行业平均", "取中位数", "反推",
)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    config_path = Path(args.config).resolve()
    config = _read_json(config_path)
    run_dir = _resolve_config_path(config_path, config["output_dir"]) / args.run_name
    metadata = _read_json(run_dir / "run_metadata.json")
    preflight = _read_json(run_dir / "preflight.json")
    models = list(metadata["models"])
    if len(models) != 2:
        raise ValueError("配对报告要求恰好两个模型")

    expected = list(metadata["selected_plan_ids"])
    results = {
        model: latest_by_plan(run_dir / f"{safe_model_name(model)}.jsonl")
        for model in models
    }
    missing = {
        model: [plan_id for plan_id in expected if plan_id not in results[model]]
        for model in models
    }
    if any(missing.values()):
        raise ValueError(f"仍有缺失结果: {missing}")

    ordered = {
        model: [results[model][plan_id] for plan_id in expected]
        for model in models
    }
    both_success_ids = [
        plan_id for plan_id in expected
        if all(results[model][plan_id].get("status") == "success" for model in models)
    ]
    single_turn = {
        model: latest_by_plan(_resolve_config_path(
            config_path,
            config["single_turn_results"][model],
        ))
        for model in models
    }
    single_missing = {
        model: [plan_id for plan_id in expected if plan_id not in single_turn[model]]
        for model in models
    }
    if any(single_missing.values()):
        raise ValueError(f"单轮基线缺少配对结果: {single_missing}")
    summary = {
        "run_name": args.run_name,
        "model_order": models,
        "selected_count": len(expected),
        "both_success_count": len(both_success_ids),
        "dataset_sha256": preflight["dataset_sha256"],
        "exact_prompt_leakage": preflight.get("exact_prompt_leakage") or {},
        "models": {
            model: {
                "agent": summarize_agent(ordered[model]),
                "answer_success_only": summarize_answers([
                    record for record in ordered[model]
                    if record.get("status") == "success"
                ]),
                "answer_both_success": summarize_answers([
                    results[model][plan_id] for plan_id in both_success_ids
                ]),
                "by_task_type": summarize_by_task_type(ordered[model]),
                "single_turn_baseline": summarize_answers([
                    single_turn[model][plan_id] for plan_id in expected
                ]),
            }
            for model in models
        },
    }
    _write_json(run_dir / "summary.json", summary)
    (run_dir / "report.md").write_text(
        render_markdown(summary),
        encoding="utf-8",
        newline="\n",
    )
    review_rows, key_rows = build_blind_review(
        results,
        plan_ids=both_success_ids,
        models=models,
        size=int(config.get("human_review_size", 30)),
        seed=int(config.get("seed", 42)),
    )
    write_jsonl(run_dir / "blind_review.jsonl", review_rows)
    write_jsonl(run_dir / "blind_review_key.jsonl", key_rows)
    print(f"Agent 配对报告: {run_dir / 'report.md'}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-name", default="full")
    return parser


def latest_by_plan(path: Path) -> dict[str, dict[str, Any]]:
    return {
        str(record["plan_id"]): record
        for record in _read_jsonl(path)
        if record.get("plan_id")
    }


def summarize_agent(records: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(records)
    success = sum(record.get("status") == "success" for record in records)
    case_passed = sum(bool(record.get("case_passed")) for record in records)
    tool_leak = sum(bool(_tool_calls(record)) for record in records)
    duplicate_tool = sum(has_duplicate_tool_call(record) for record in records)
    rag_calls = sum(
        call.get("tool_name") == "search_knowledge"
        for record in records
        for call in _tool_calls(record)
    )
    error_classes = collections.Counter(
        str((record.get("agent") or {}).get("error_class") or record.get("framework_error"))
        for record in records
        if record.get("status") != "success"
    )
    latencies = [float(record.get("latency_seconds") or 0) for record in records]
    return {
        "count": count,
        "workflow_success_count": success,
        "workflow_success_rate": _rate(success, count),
        "case_pass_count": case_passed,
        "case_pass_rate": _rate(case_passed, count),
        "direct_route_count": sum(
            record.get("status") == "success" and not _tool_calls(record)
            for record in records
        ),
        "direct_route_rate": _rate(
            sum(record.get("status") == "success" and not _tool_calls(record) for record in records),
            count,
        ),
        "tool_leakage_samples": tool_leak,
        "tool_leakage_rate": _rate(tool_leak, count),
        "duplicate_tool_samples": duplicate_tool,
        "duplicate_tool_rate": _rate(duplicate_tool, count),
        "rag_tool_calls": rag_calls,
        "failure_error_classes": dict(sorted(error_classes.items())),
        "latency_mean_seconds": round(statistics.mean(latencies), 4) if latencies else 0.0,
        "latency_p50_seconds": round(percentile(latencies, 0.50), 4),
        "latency_p95_seconds": round(percentile(latencies, 0.95), 4),
    }


def summarize_answers(records: list[dict[str, Any]]) -> dict[str, Any]:
    char_f1: list[float] = []
    bigram_f1: list[float] = []
    fourgram_f1: list[float] = []
    output_chars: list[int] = []
    novel_count = 0
    speculative_count = 0
    for record in records:
        prediction = str(record.get("prediction") or "")
        reference = str(record.get("reference") or "")
        char_f1.append(multiset_f1(ngrams(prediction, 1), ngrams(reference, 1)))
        bigram_f1.append(multiset_f1(ngrams(prediction, 2), ngrams(reference, 2)))
        fourgram_f1.append(multiset_f1(ngrams(prediction, 4), ngrams(reference, 4)))
        output_chars.append(len(prediction))
        if novel_numeric_claims(record):
            novel_count += 1
            if any(marker in prediction for marker in SPECULATIVE_MARKERS):
                speculative_count += 1
    count = len(records)
    return {
        "count": count,
        "char_f1": _mean(char_f1, 6),
        "char_bigram_f1": _mean(bigram_f1, 6),
        "char_4gram_f1": _mean(fourgram_f1, 6),
        "output_chars_mean": _mean(output_chars, 2),
        "novel_numeric_claim_samples": novel_count,
        "novel_numeric_claim_rate": _rate(novel_count, count),
        "speculative_numeric_risk_samples": speculative_count,
        "speculative_numeric_risk_rate": _rate(speculative_count, count),
    }


def summarize_by_task_type(records: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for record in records:
        grouped[str(record["task_type"])].append(record)
    return {
        task_type: {
            "agent": summarize_agent(items),
            "answer_success_only": summarize_answers([
                item for item in items if item.get("status") == "success"
            ]),
        }
        for task_type, items in sorted(grouped.items())
    }


def has_duplicate_tool_call(record: dict[str, Any]) -> bool:
    seen: set[str] = set()
    for call in _tool_calls(record):
        key = json.dumps(
            [call.get("tool_name"), call.get("arguments") or {}],
            ensure_ascii=False,
            sort_keys=True,
        )
        if key in seen:
            return True
        seen.add(key)
    return False


def _tool_calls(record: dict[str, Any]) -> list[dict[str, Any]]:
    return list((record.get("agent") or {}).get("tool_calls") or [])


def ngrams(text: str, size: int) -> collections.Counter[str]:
    normalized = SPACE_PATTERN.sub("", text).lower()
    if len(normalized) < size:
        return collections.Counter([normalized]) if normalized else collections.Counter()
    return collections.Counter(
        normalized[index:index + size]
        for index in range(len(normalized) - size + 1)
    )


def multiset_f1(
    left: collections.Counter[str],
    right: collections.Counter[str],
) -> float:
    overlap = sum((left & right).values())
    left_total = sum(left.values())
    right_total = sum(right.values())
    if not left_total or not right_total:
        return 0.0
    precision = overlap / left_total
    recall = overlap / right_total
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def numeric_claims(text: str) -> set[str]:
    claims: set[str] = set()
    for match in NUMBER_PATTERN.finditer(text):
        number = match.group("number")
        unit = (match.group("unit") or "").lower()
        if not unit and float(number) <= 10:
            continue
        claims.add(f"{number}{unit}")
    return claims


def novel_numeric_claims(record: dict[str, Any]) -> list[str]:
    prompt = f"{record.get('instruction', '')}\n{record.get('input', '')}"
    return sorted(
        numeric_claims(str(record.get("prediction") or "")) - numeric_claims(prompt),
    )


def percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * ratio
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def render_markdown(summary: dict[str, Any]) -> str:
    base_model, lora_model = summary["model_order"]
    base = summary["models"][base_model]
    lora = summary["models"][lora_model]
    ba, la = base["agent"], lora["agent"]
    br, lr = base["answer_both_success"], lora["answer_both_success"]
    bs, ls = base["single_turn_baseline"], lora["single_turn_baseline"]
    return f"""# JobPilot 500 条 Base / LoRA Agent 配对评测

## 范围

- 选择样本：{summary['selected_count']}
- 两模型都成功：{summary['both_success_count']}
- Base：`{base_model}`
- LoRA：`{lora_model}`
- 数据集 SHA256：`{summary['dataset_sha256']}`
- RAG：请求级排除 `search_knowledge`

## Agent 行为

| 指标 | Base | LoRA |
|---|---:|---:|
| 工作流成功率 | {ba['workflow_success_rate']:.2%} | {la['workflow_success_rate']:.2%} |
| 完整 case 通过率 | {ba['case_pass_rate']:.2%} | {la['case_pass_rate']:.2%} |
| 无工具直答率 | {ba['direct_route_rate']:.2%} | {la['direct_route_rate']:.2%} |
| 错误工具调用率 | {ba['tool_leakage_rate']:.2%} | {la['tool_leakage_rate']:.2%} |
| 重复工具调用率 | {ba['duplicate_tool_rate']:.2%} | {la['duplicate_tool_rate']:.2%} |
| RAG 工具调用次数 | {ba['rag_tool_calls']} | {la['rag_tool_calls']} |
| 平均延迟 | {ba['latency_mean_seconds']:.3f}s | {la['latency_mean_seconds']:.3f}s |
| P95 延迟 | {ba['latency_p95_seconds']:.3f}s | {la['latency_p95_seconds']:.3f}s |

## 两模型都成功的回答质量

| 指标 | Base Agent | LoRA Agent |
|---|---:|---:|
| 字符 F1 | {br['char_f1']:.4f} | {lr['char_f1']:.4f} |
| 字符 2-gram F1 | {br['char_bigram_f1']:.4f} | {lr['char_bigram_f1']:.4f} |
| 字符 4-gram F1 | {br['char_4gram_f1']:.4f} | {lr['char_4gram_f1']:.4f} |
| 平均输出字符 | {br['output_chars_mean']:.1f} | {lr['output_chars_mean']:.1f} |
| 新增数字样本率 | {br['novel_numeric_claim_rate']:.2%} | {lr['novel_numeric_claim_rate']:.2%} |
| 推测性数字风险率 | {br['speculative_numeric_risk_rate']:.2%} | {lr['speculative_numeric_risk_rate']:.2%} |

## 单轮直调与 Agent 包装差异

| 指标 | Base 单轮 | Base Agent | LoRA 单轮 | LoRA Agent |
|---|---:|---:|---:|---:|
| 字符 F1 | {bs['char_f1']:.4f} | {br['char_f1']:.4f} | {ls['char_f1']:.4f} | {lr['char_f1']:.4f} |
| 2-gram F1 | {bs['char_bigram_f1']:.4f} | {br['char_bigram_f1']:.4f} | {ls['char_bigram_f1']:.4f} | {lr['char_bigram_f1']:.4f} |
| 4-gram F1 | {bs['char_4gram_f1']:.4f} | {br['char_4gram_f1']:.4f} | {ls['char_4gram_f1']:.4f} | {lr['char_4gram_f1']:.4f} |

## 解读边界

- 这 500 条没有业务资源上下文，正确 Agent 路线通常是无工具直答。
- 工具路由能力仍以专门的 10 条 Agent 场景集为准。
- 自动文本指标不能替代事实核验；盲评材料见 `blind_review.jsonl`。
"""


def build_blind_review(
    results: dict[str, dict[str, dict[str, Any]]],
    *,
    plan_ids: list[str],
    models: list[str],
    size: int,
    seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    randomizer = random.Random(seed)
    selected = list(plan_ids)
    randomizer.shuffle(selected)
    selected = selected[:min(size, len(selected))]
    review_rows: list[dict[str, Any]] = []
    key_rows: list[dict[str, Any]] = []
    for index, plan_id in enumerate(selected, start=1):
        base = results[models[0]][plan_id]
        lora = results[models[1]][plan_id]
        base_is_a = randomizer.choice([True, False])
        review_id = f"agent-blind-{index:04d}"
        review_rows.append({
            "review_id": review_id,
            "plan_id": plan_id,
            "task_type": base["task_type"],
            "instruction": base["instruction"],
            "input": base.get("input", ""),
            "answer_a": base["prediction"] if base_is_a else lora["prediction"],
            "answer_b": lora["prediction"] if base_is_a else base["prediction"],
            "review": {
                "preferred": "",
                "task_correctness_a_1_to_5": None,
                "task_correctness_b_1_to_5": None,
                "faithfulness_a_1_to_5": None,
                "faithfulness_b_1_to_5": None,
                "clarity_a_1_to_5": None,
                "clarity_b_1_to_5": None,
                "notes": "",
            },
        })
        key_rows.append({
            "review_id": review_id,
            "answer_a_model": models[0] if base_is_a else models[1],
            "answer_b_model": models[1] if base_is_a else models[0],
        })
    return review_rows, key_rows


def write_jsonl(path: Path, values: Iterable[dict[str, Any]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as file:
        for value in values:
            json.dump(value, file, ensure_ascii=False)
            file.write("\n")
    temporary.replace(path)


def _rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def _mean(values: list[float] | list[int], digits: int) -> float:
    return round(statistics.mean(values), digits) if values else 0.0


if __name__ == "__main__":
    raise SystemExit(main())
