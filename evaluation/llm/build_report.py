#!/usr/bin/env python3
"""汇总 Base/LoRA 配对结果，生成自动指标、数字风险诊断和盲评材料。"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import random
import re
import statistics
from pathlib import Path
from typing import Any, Iterable


SPACE_PATTERN = re.compile(r"\s+")
NUMBER_PATTERN = re.compile(
    r"(?P<number>\d+(?:\.\d+)?)\s*"
    r"(?P<unit>%|％|ms|毫秒|s|秒|分钟|小时|天|万|亿|人|次|倍|GB|MB|KB|QPS)?",
    re.IGNORECASE,
)
SPECULATIVE_MARKERS = (
    "估算",
    "估计",
    "假设为",
    "假定为",
    "可以写成",
    "可写为",
    "行业平均",
    "取中位数",
    "反推",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-name", default="full")
    parser.add_argument("--review-size", type=int, default=None)
    return parser.parse_args()


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as error:
                raise ValueError(f"{path}:{line_number} JSON 无效") from error
    return records


def write_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(value, file, ensure_ascii=False, indent=2)
        file.write("\n")
    temporary.replace(path)


def write_jsonl(path: Path, values: Iterable[dict[str, Any]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as file:
        for value in values:
            json.dump(value, file, ensure_ascii=False)
            file.write("\n")
    temporary.replace(path)


def safe_model_name(model: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", model)


def latest_success_by_plan(path: Path) -> dict[str, dict[str, Any]]:
    """同一 plan 重跑时，以最后一条成功结果为准。"""
    selected: dict[str, dict[str, Any]] = {}
    for record in read_jsonl(path):
        if record.get("status") == "success":
            selected[str(record["plan_id"])] = record
    return selected


def normalize_text(text: str) -> str:
    return SPACE_PATTERN.sub("", text).lower()


def ngrams(text: str, size: int) -> collections.Counter[str]:
    normalized = normalize_text(text)
    if len(normalized) < size:
        return collections.Counter([normalized]) if normalized else collections.Counter()
    return collections.Counter(
        normalized[index : index + size]
        for index in range(len(normalized) - size + 1)
    )


def multiset_f1(left: collections.Counter[str], right: collections.Counter[str]) -> float:
    overlap = sum((left & right).values())
    left_total = sum(left.values())
    right_total = sum(right.values())
    if left_total == 0 or right_total == 0:
        return 0.0
    precision = overlap / left_total
    recall = overlap / right_total
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def reference_metrics(prediction: str, reference: str) -> dict[str, float]:
    return {
        "char_f1": multiset_f1(ngrams(prediction, 1), ngrams(reference, 1)),
        "char_bigram_f1": multiset_f1(ngrams(prediction, 2), ngrams(reference, 2)),
        "char_4gram_f1": multiset_f1(ngrams(prediction, 4), ngrams(reference, 4)),
    }


def numeric_claims(text: str) -> set[str]:
    """忽略 1～10 的裸序号，只保留带单位或较大的数字声明。"""
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
    prompt_claims = numeric_claims(prompt)
    prediction_claims = numeric_claims(str(record["prediction"]))
    return sorted(prediction_claims - prompt_claims)


def percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * ratio
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def summarize_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    char_f1: list[float] = []
    bigram_f1: list[float] = []
    fourgram_f1: list[float] = []
    latencies: list[float] = []
    completion_tokens: list[float] = []
    novel_number_count = 0
    speculative_number_count = 0

    for record in records:
        scores = reference_metrics(str(record["prediction"]), str(record["reference"]))
        char_f1.append(scores["char_f1"])
        bigram_f1.append(scores["char_bigram_f1"])
        fourgram_f1.append(scores["char_4gram_f1"])
        latencies.append(float(record.get("latency_seconds", 0)))
        completion_tokens.append(float(record.get("usage", {}).get("completion_tokens") or 0))
        novel = novel_numeric_claims(record)
        if novel:
            novel_number_count += 1
            prediction = str(record["prediction"])
            if any(marker in prediction for marker in SPECULATIVE_MARKERS):
                speculative_number_count += 1

    count = len(records)
    return {
        "count": count,
        "char_f1": round(statistics.mean(char_f1), 6) if char_f1 else 0.0,
        "char_bigram_f1": round(statistics.mean(bigram_f1), 6) if bigram_f1 else 0.0,
        "char_4gram_f1": round(statistics.mean(fourgram_f1), 6) if fourgram_f1 else 0.0,
        "latency_mean_seconds": round(statistics.mean(latencies), 4) if latencies else 0.0,
        "latency_p50_seconds": round(percentile(latencies, 0.50), 4),
        "latency_p95_seconds": round(percentile(latencies, 0.95), 4),
        "completion_tokens_mean": round(statistics.mean(completion_tokens), 2)
        if completion_tokens
        else 0.0,
        "novel_numeric_claim_samples": novel_number_count,
        "novel_numeric_claim_rate": round(novel_number_count / count, 6) if count else 0.0,
        "speculative_numeric_risk_samples": speculative_number_count,
        "speculative_numeric_risk_rate": round(speculative_number_count / count, 6)
        if count
        else 0.0,
    }


def by_task_type(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for record in records:
        grouped[str(record["task_type"])].append(record)
    return {
        task_type: summarize_records(task_records)
        for task_type, task_records in sorted(grouped.items())
    }


def paired_delta(base: dict[str, Any], lora: dict[str, Any]) -> dict[str, float]:
    keys = (
        "char_f1",
        "char_bigram_f1",
        "char_4gram_f1",
        "latency_mean_seconds",
        "completion_tokens_mean",
        "novel_numeric_claim_rate",
        "speculative_numeric_risk_rate",
    )
    return {key: round(float(lora[key]) - float(base[key]), 6) for key in keys}


def select_blind_review(
    pairs: list[dict[str, Any]],
    *,
    size: int,
    seed: int,
    base_model: str,
    lora_model: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for pair in pairs:
        grouped[pair["base"]["task_type"]].append(pair)

    randomizer = random.Random(seed)
    for task_pairs in grouped.values():
        randomizer.shuffle(task_pairs)

    selected: list[dict[str, Any]] = []
    task_types = sorted(grouped)
    while len(selected) < min(size, len(pairs)):
        made_progress = False
        for task_type in task_types:
            if grouped[task_type] and len(selected) < size:
                selected.append(grouped[task_type].pop())
                made_progress = True
        if not made_progress:
            break

    review_rows: list[dict[str, Any]] = []
    key_rows: list[dict[str, Any]] = []
    for review_index, pair in enumerate(selected, start=1):
        base_record = pair["base"]
        lora_record = pair["lora"]
        base_is_a = randomizer.choice([True, False])
        answer_a = base_record["prediction"] if base_is_a else lora_record["prediction"]
        answer_b = lora_record["prediction"] if base_is_a else base_record["prediction"]
        review_id = f"blind-{review_index:04d}"
        review_rows.append(
            {
                "review_id": review_id,
                "plan_id": base_record["plan_id"],
                "task_type": base_record["task_type"],
                "instruction": base_record["instruction"],
                "input": base_record.get("input", ""),
                "answer_a": answer_a,
                "answer_b": answer_b,
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
            }
        )
        key_rows.append(
            {
                "review_id": review_id,
                "answer_a_model": base_model if base_is_a else lora_model,
                "answer_b_model": lora_model if base_is_a else base_model,
            }
        )
    return review_rows, key_rows


def markdown_report(summary: dict[str, Any]) -> str:
    models = summary["models"]
    base_model, lora_model = summary["model_order"][:2]
    base = models[base_model]["overall"]
    lora = models[lora_model]["overall"]
    delta = summary["paired_delta_lora_minus_base"]
    return f"""# JobPilot Base / LoRA 独立评测报告

## 评测范围

- 配对样本：{summary['paired_count']}
- Base：`{base_model}`
- LoRA：`{lora_model}`
- 数据集 SHA256：`{summary['dataset_sha256']}`
- 自动指标只用于诊断，不能替代人工盲评。

## 整体指标

| 指标 | Base | LoRA | LoRA - Base |
|---|---:|---:|---:|
| 字符 F1 | {base['char_f1']:.4f} | {lora['char_f1']:.4f} | {delta['char_f1']:+.4f} |
| 字符 2-gram F1 | {base['char_bigram_f1']:.4f} | {lora['char_bigram_f1']:.4f} | {delta['char_bigram_f1']:+.4f} |
| 字符 4-gram F1 | {base['char_4gram_f1']:.4f} | {lora['char_4gram_f1']:.4f} | {delta['char_4gram_f1']:+.4f} |
| 平均延迟（秒） | {base['latency_mean_seconds']:.4f} | {lora['latency_mean_seconds']:.4f} | {delta['latency_mean_seconds']:+.4f} |
| 平均输出 Token | {base['completion_tokens_mean']:.2f} | {lora['completion_tokens_mean']:.2f} | {delta['completion_tokens_mean']:+.2f} |
| 新增数字样本率 | {base['novel_numeric_claim_rate']:.2%} | {lora['novel_numeric_claim_rate']:.2%} | {delta['novel_numeric_claim_rate']:+.2%} |
| 推测性数字风险率 | {base['speculative_numeric_risk_rate']:.2%} | {lora['speculative_numeric_risk_rate']:.2%} | {delta['speculative_numeric_risk_rate']:+.2%} |

## 解读边界

- 文本相似度高，不代表事实更可靠；本数据集的部分参考答案本身包含估算数字。
- “新增数字”是风险信号，不等价于造假，需要结合输入语境和盲评判断。
- 是否部署 LoRA，应综合任务正确性、真实性、清晰度三项人工盲评，而不是只看单个自动指标。

## 盲评

- 待填写：`blind_review.jsonl`
- 揭盲映射：`blind_review_key.jsonl`，评审完成前不要打开。
- `preferred` 只允许填写 `A`、`B` 或 `TIE`。
"""


def main() -> None:
    args = parse_args()
    config = read_json(Path(args.config).resolve())
    output_dir = Path(config["output_dir"]).resolve() / args.run_name
    metadata = read_json(output_dir / "run_metadata.json")
    preflight = read_json(output_dir / "preflight.json")
    models = list(metadata["models"])
    if len(models) != 2:
        raise ValueError("配对报告当前要求恰好两个模型")

    results = {
        model: latest_success_by_plan(output_dir / f"{safe_model_name(model)}.jsonl")
        for model in models
    }
    expected_plan_ids = list(metadata["selected_plan_ids"])
    missing = {
        model: [plan_id for plan_id in expected_plan_ids if plan_id not in results[model]]
        for model in models
    }
    if any(missing.values()):
        raise ValueError(f"仍有缺失的成功结果：{missing}")

    pairs = [
        {
            "base": results[models[0]][plan_id],
            "lora": results[models[1]][plan_id],
        }
        for plan_id in expected_plan_ids
    ]
    for pair in pairs:
        if pair["base"]["request_sha256"] == pair["lora"]["request_sha256"]:
            raise ValueError("请求哈希不应相同，因为 model 字段不同")
        if pair["base"]["prompt_sha256"] != pair["lora"]["prompt_sha256"]:
            raise ValueError(f"输入未配对：{pair['base']['plan_id']}")

    per_model: dict[str, Any] = {}
    for model in models:
        ordered = [results[model][plan_id] for plan_id in expected_plan_ids]
        per_model[model] = {
            "overall": summarize_records(ordered),
            "by_task_type": by_task_type(ordered),
        }

    summary = {
        "run_name": args.run_name,
        "model_order": models,
        "paired_count": len(pairs),
        "dataset_sha256": preflight["dataset_sha256"],
        "manifest_sha256": preflight["manifest_sha256"],
        "exact_prompt_leakage": preflight["exact_prompt_leakage"],
        "models": per_model,
        "paired_delta_lora_minus_base": paired_delta(
            per_model[models[0]]["overall"], per_model[models[1]]["overall"]
        ),
    }
    write_json(output_dir / "summary.json", summary)
    (output_dir / "report.md").write_text(
        markdown_report(summary), encoding="utf-8", newline="\n"
    )

    review_size = args.review_size or int(config["human_review_size"])
    review_rows, key_rows = select_blind_review(
        pairs,
        size=review_size,
        seed=int(config["seed"]),
        base_model=models[0],
        lora_model=models[1],
    )
    write_jsonl(output_dir / "blind_review.jsonl", review_rows)
    write_jsonl(output_dir / "blind_review_key.jsonl", key_rows)

    print(f"配对报告生成完成：{len(pairs)} 条")
    print(f"报告：{output_dir / 'report.md'}")
    print(f"盲评：{output_dir / 'blind_review.jsonl'}")


if __name__ == "__main__":
    main()
