"""汇总 Base/LoRA Agent + Hybrid RAG 成对评测结果。"""

from __future__ import annotations

import argparse
import collections
import csv
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
from app.eval.agent_pair_report import has_duplicate_tool_call, percentile, write_jsonl
from app.eval.agent_rag_pair_cli import extract_retrieved_hits, search_call_succeeded


TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+|[\u3400-\u9fff]+")


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    config_path = Path(args.config).resolve()
    config = _read_json(config_path)
    run_dir = _resolve_config_path(config_path, str(config["output_dir"])) / args.run_name
    metadata = _read_json(run_dir / "run_metadata.json")
    preflight = _read_json(run_dir / "preflight.json")
    models = list(metadata["models"])
    if len(models) != 2:
        raise ValueError("成对报告要求恰好两个模型")

    expected = list(metadata["selected_case_ids"])
    results = {
        model: latest_by_case(run_dir / f"{safe_model_name(model)}.jsonl")
        for model in models
    }
    missing = {
        model: [case_id for case_id in expected if case_id not in results[model]]
        for model in models
    }
    if any(missing.values()):
        raise ValueError(f"仍有缺失结果: {missing}")
    ordered = {
        model: [results[model][case_id] for case_id in expected]
        for model in models
    }
    both_success_ids = [
        case_id for case_id in expected
        if all(results[model][case_id].get("status") == "success" for model in models)
    ]
    both_rag_route_ids = [
        case_id for case_id in both_success_ids
        if all(rag_route_passed(results[model][case_id]) for model in models)
    ]
    per_case_metrics = {
        model: {
            case_id: score_record(results[model][case_id])
            for case_id in expected
        }
        for model in models
    }
    paired = paired_comparison(
        results,
        per_case_metrics,
        case_ids=both_success_ids,
        models=models,
        seed=int(config.get("seed", 42)),
    )
    paired_rag_route = paired_comparison(
        results,
        per_case_metrics,
        case_ids=both_rag_route_ids,
        models=models,
        seed=int(config.get("seed", 42)),
    )
    summary = {
        "run_name": args.run_name,
        "model_order": models,
        "selected_count": len(expected),
        "both_success_count": len(both_success_ids),
        "both_rag_route_count": len(both_rag_route_ids),
        "dataset_sha256": preflight["dataset_sha256"],
        "document_set_sha256": preflight["fixture"]["document_set_sha256"],
        "rag": preflight["rag"],
        "models": {
            model: {
                "agent": summarize_agent(ordered[model]),
                "retrieval": summarize_metric_group(
                    [per_case_metrics[model][case_id]["retrieval"] for case_id in expected],
                ),
                "retrieval_search_selected": summarize_metric_group([
                    per_case_metrics[model][case_id]["retrieval"]
                    for case_id in expected
                    if rag_facts(results[model][case_id])["search_call_count"] > 0
                ]),
                "answer_all_success": summarize_metric_group([
                    per_case_metrics[model][case_id]["answer"]
                    for case_id in expected
                    if results[model][case_id].get("status") == "success"
                ]),
                "answer_both_success": summarize_metric_group([
                    per_case_metrics[model][case_id]["answer"]
                    for case_id in both_success_ids
                ]),
                "answer_both_rag_route": summarize_metric_group([
                    per_case_metrics[model][case_id]["answer"]
                    for case_id in both_rag_route_ids
                ]),
                "by_domain": summarize_by_domain(
                    ordered[model], per_case_metrics[model],
                ),
            }
            for model in models
        },
        "paired": paired,
        "paired_both_rag_route": paired_rag_route,
    }
    _write_json(run_dir / "summary.json", summary)
    (run_dir / "report.md").write_text(
        render_markdown(summary),
        encoding="utf-8",
        newline="\n",
    )
    write_case_csv(
        run_dir / "paired_cases.csv",
        results,
        per_case_metrics,
        case_ids=expected,
        models=models,
    )
    review_rows, key_rows = build_blind_review(
        results,
        case_ids=both_success_ids,
        models=models,
        size=int(config.get("human_review_size", 40)),
        seed=int(config.get("seed", 42)),
    )
    write_jsonl(run_dir / "blind_review.jsonl", review_rows)
    write_jsonl(run_dir / "blind_review_key.jsonl", key_rows)
    print(f"Agent + RAG 配对报告: {run_dir / 'report.md'}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-name", default="full")
    return parser


def latest_by_case(path: Path) -> dict[str, dict[str, Any]]:
    return {
        str(row["case_id"]): row
        for row in _read_jsonl(path)
        if row.get("case_id")
    }


def summarize_agent(records: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(records)
    workflow_success = sum(row.get("status") == "success" for row in records)
    facts = [rag_facts(row) for row in records]
    route_pass = sum(
        row.get("status") == "success"
        and item["search_call_count"] == 1
        and item["successful_search_call_count"] == 1
        and item["correct_knowledge_base_call_count"] == 1
        for row, item in zip(records, facts)
    )
    search_samples = sum(item["search_call_count"] > 0 for item in facts)
    direct_samples = count - search_samples
    single_search = sum(item["search_call_count"] == 1 for item in facts)
    successful_search = sum(
        item["successful_search_call_count"] > 0 for item in facts
    )
    correct_kb = sum(
        item["correct_knowledge_base_call_count"] == item["search_call_count"]
        and item["search_call_count"] > 0
        for item in facts
    )
    duplicate = sum(has_duplicate_tool_call(row) for row in records)
    multi_search = sum(item["search_call_count"] > 1 for item in facts)
    wrong_tool = sum(
        any(call.get("tool_name") != "search_knowledge" for call in _tool_calls(row))
        for row in records
    )
    latencies = [float(row.get("latency_seconds") or 0) for row in records]
    tool_latencies = [
        float(call.get("latency_ms") or 0)
        for row in records
        for call in _tool_calls(row)
        if call.get("tool_name") == "search_knowledge"
    ]
    errors = collections.Counter(
        str((row.get("agent") or {}).get("error_class") or row.get("framework_error"))
        for row in records
        if row.get("status") != "success"
    )
    return {
        "count": count,
        "workflow_success_count": workflow_success,
        "workflow_success_rate": rate(workflow_success, count),
        "rag_route_pass_count": route_pass,
        "rag_route_pass_rate": rate(route_pass, count),
        "search_selected_count": search_samples,
        "search_selected_rate": rate(search_samples, count),
        "direct_route_count": direct_samples,
        "direct_route_rate": rate(direct_samples, count),
        "single_search_count": single_search,
        "single_search_rate": rate(single_search, count),
        "successful_search_count": successful_search,
        "successful_search_rate": rate(successful_search, count),
        "correct_kb_sample_count": correct_kb,
        "correct_kb_sample_rate": rate(correct_kb, count),
        "duplicate_tool_sample_count": duplicate,
        "duplicate_tool_sample_rate": rate(duplicate, count),
        "multi_search_sample_count": multi_search,
        "multi_search_sample_rate": rate(multi_search, count),
        "wrong_tool_sample_count": wrong_tool,
        "wrong_tool_sample_rate": rate(wrong_tool, count),
        "failure_error_classes": dict(sorted(errors.items())),
        "latency_mean_seconds": mean(latencies),
        "latency_p50_seconds": round(percentile(latencies, 0.5), 4),
        "latency_p95_seconds": round(percentile(latencies, 0.95), 4),
        "search_latency_mean_ms": mean(tool_latencies),
        "search_latency_p95_ms": round(percentile(tool_latencies, 0.95), 3),
    }


def score_record(record: dict[str, Any]) -> dict[str, dict[str, float]]:
    hits = list(rag_facts(record)["retrieved_hits"])
    source_document = str(record.get("source_document") or "")
    source_ranks = [
        index for index, hit in enumerate(hits, start=1)
        if hit.get("document_title") == source_document
    ]
    target_text = "\n".join(
        str(hit.get("content") or "")
        for hit in hits
        if hit.get("document_title") == source_document
    )
    excerpt_tokens = tokenize(str(record.get("supporting_excerpt") or ""))
    retrieved_tokens = tokenize(target_text)
    retrieval = {
        "recall_at_5": 1.0 if source_ranks else 0.0,
        "mrr": 1.0 / min(source_ranks) if source_ranks else 0.0,
        "excerpt_recall": token_recall(excerpt_tokens, retrieved_tokens),
    }
    reference_tokens = tokenize(str(record.get("reference_answer") or ""))
    prediction_tokens = tokenize(str(record.get("prediction") or ""))
    token_f1 = multiset_f1(reference_tokens, prediction_tokens)
    rouge_l = rouge_l_f1(reference_tokens, prediction_tokens)
    source_support = token_recall(prediction_tokens, excerpt_tokens)
    answer = {
        "answer_score": (token_f1 + rouge_l) / 2,
        "token_f1": token_f1,
        "rouge_l": rouge_l,
        "faithfulness": source_support,
        "source_support": source_support,
    }
    return {"retrieval": retrieval, "answer": answer}


def summarize_metric_group(values: list[dict[str, float]]) -> dict[str, float | int]:
    if not values:
        return {"count": 0}
    keys = sorted(values[0])
    return {
        "count": len(values),
        **{key: mean([item[key] for item in values]) for key in keys},
    }


def summarize_by_domain(
    records: list[dict[str, Any]],
    metrics: dict[str, dict[str, dict[str, float]]],
) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in records:
        grouped[source_domain(str(row["source_document"]))].append(row)
    return {
        domain: {
            "count": len(items),
            "agent": summarize_agent(items),
            "retrieval": summarize_metric_group([
                metrics[row["case_id"]]["retrieval"] for row in items
            ]),
            "answer": summarize_metric_group([
                metrics[row["case_id"]]["answer"]
                for row in items if row.get("status") == "success"
            ]),
        }
        for domain, items in sorted(grouped.items())
    }


def paired_comparison(
    results: dict[str, dict[str, dict[str, Any]]],
    metrics: dict[str, dict[str, dict[str, dict[str, float]]]],
    *,
    case_ids: list[str],
    models: list[str],
    seed: int,
) -> dict[str, Any]:
    base_model, lora_model = models
    deltas = [
        metrics[lora_model][case_id]["answer"]["answer_score"]
        - metrics[base_model][case_id]["answer"]["answer_score"]
        for case_id in case_ids
    ]
    wins = sum(delta > 1e-12 for delta in deltas)
    losses = sum(delta < -1e-12 for delta in deltas)
    ties = len(deltas) - wins - losses
    low, high = bootstrap_mean_ci(deltas, seed=seed)
    source_hit_pairs = {
        "base_only": 0,
        "lora_only": 0,
        "both": 0,
        "neither": 0,
    }
    for case_id in case_ids:
        base_hit = metrics[base_model][case_id]["retrieval"]["recall_at_5"] > 0
        lora_hit = metrics[lora_model][case_id]["retrieval"]["recall_at_5"] > 0
        key = "both" if base_hit and lora_hit else (
            "base_only" if base_hit else "lora_only" if lora_hit else "neither"
        )
        source_hit_pairs[key] += 1
    return {
        "count": len(case_ids),
        "lora_win_count": wins,
        "tie_count": ties,
        "base_win_count": losses,
        "lora_minus_base_answer_score": mean(deltas),
        "bootstrap_95_ci": [low, high],
        "source_hit_pairs": source_hit_pairs,
    }


def bootstrap_mean_ci(
    values: list[float],
    *,
    seed: int,
    samples: int = 5000,
) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    rng = random.Random(seed)
    means = [
        statistics.mean(rng.choice(values) for _ in values)
        for _ in range(samples)
    ]
    means.sort()
    return (
        round(means[math.floor(0.025 * (samples - 1))], 6),
        round(means[math.ceil(0.975 * (samples - 1))], 6),
    )


def render_markdown(summary: dict[str, Any]) -> str:
    base_model, lora_model = summary["model_order"]
    base, lora = summary["models"][base_model], summary["models"][lora_model]
    ba, la = base["agent"], lora["agent"]
    br, lr = base["retrieval"], lora["retrieval"]
    brs, lrs = base["retrieval_search_selected"], lora["retrieval_search_selected"]
    bq, lq = base["answer_both_success"], lora["answer_both_success"]
    bqr, lqr = base["answer_both_rag_route"], lora["answer_both_rag_route"]
    paired = summary["paired"]
    paired_rag = summary["paired_both_rag_route"]
    rag = summary["rag"]
    return f"""# JobPilot Base / LoRA Agent + Hybrid RAG 配对评测

## 实验口径

- 问题数：{summary['selected_count']}
- 两模型工作流均成功：{summary['both_success_count']}
- Base Agent：`{base_model}`
- LoRA Agent：`{lora_model}`
- 检索：`{rag['strategy']}`，向量/BM25权重 `{rag['vector_weight']}:{rag['bm25_weight']}`
- Reranker：`{rag['reranker_model']}`
- 严格模式：vector fail-open=`{rag['vector_fail_open']}`，reranker fail-open=`{rag['reranker_fail_open']}`

## Agent行为

| 指标 | Base Agent + RAG | LoRA Agent + RAG |
|---|---:|---:|
| 工作流成功率 | {ba['workflow_success_rate']:.2%} | {la['workflow_success_rate']:.2%} |
| 完整RAG路由通过率 | {ba['rag_route_pass_rate']:.2%} | {la['rag_route_pass_rate']:.2%} |
| 选择检索工具率 | {ba['search_selected_rate']:.2%} | {la['search_selected_rate']:.2%} |
| 单次检索率 | {ba['single_search_rate']:.2%} | {la['single_search_rate']:.2%} |
| 检索成功率 | {ba['successful_search_rate']:.2%} | {la['successful_search_rate']:.2%} |
| 知识库ID正确率 | {ba['correct_kb_sample_rate']:.2%} | {la['correct_kb_sample_rate']:.2%} |
| 无检索直答率 | {ba['direct_route_rate']:.2%} | {la['direct_route_rate']:.2%} |
| 多次检索率 | {ba['multi_search_sample_rate']:.2%} | {la['multi_search_sample_rate']:.2%} |
| 参数完全重复调用率 | {ba['duplicate_tool_sample_rate']:.2%} | {la['duplicate_tool_sample_rate']:.2%} |
| 平均端到端延迟 | {ba['latency_mean_seconds']:.3f}s | {la['latency_mean_seconds']:.3f}s |
| P95端到端延迟 | {ba['latency_p95_seconds']:.3f}s | {la['latency_p95_seconds']:.3f}s |

## 检索质量

| 指标 | Base Agent + RAG | LoRA Agent + RAG |
|---|---:|---:|
| 整体有效Source Hit / Recall@5 | {br['recall_at_5']:.4f} | {lr['recall_at_5']:.4f} |
| 选择检索后的Source Hit | {brs['recall_at_5']:.4f} | {lrs['recall_at_5']:.4f} |
| 选择检索后的MRR | {brs['mrr']:.4f} | {lrs['mrr']:.4f} |
| 选择检索后的证据召回 | {brs['excerpt_recall']:.4f} | {lrs['excerpt_recall']:.4f} |

## 两模型工作流都成功时的回答质量

| 指标 | Base Agent + RAG | LoRA Agent + RAG |
|---|---:|---:|
| Answer Score | {bq['answer_score']:.4f} | {lq['answer_score']:.4f} |
| Token F1 | {bq['token_f1']:.4f} | {lq['token_f1']:.4f} |
| ROUGE-L | {bq['rouge_l']:.4f} | {lq['rouge_l']:.4f} |
| 来源支持度 | {bq['source_support']:.4f} | {lq['source_support']:.4f} |

## 成对结论

- LoRA胜 / 平 / Base胜：{paired['lora_win_count']} / {paired['tie_count']} / {paired['base_win_count']}
- LoRA - Base Answer Score：{paired['lora_minus_base_answer_score']:+.4f}
- Bootstrap 95% CI：[{paired['bootstrap_95_ci'][0]:+.4f}, {paired['bootstrap_95_ci'][1]:+.4f}]
- 正确来源共同命中：{paired['source_hit_pairs']['both']}；仅Base命中：{paired['source_hit_pairs']['base_only']}；仅LoRA命中：{paired['source_hit_pairs']['lora_only']}；均未命中：{paired['source_hit_pairs']['neither']}

## 两模型都完成单次RAG路由的条件对比

- 配对样本数：{summary['both_rag_route_count']}
- Base / LoRA Answer Score：{bqr.get('answer_score', 0):.4f} / {lqr.get('answer_score', 0):.4f}
- LoRA胜 / 平 / Base胜：{paired_rag['lora_win_count']} / {paired_rag['tie_count']} / {paired_rag['base_win_count']}
- LoRA - Base Answer Score：{paired_rag['lora_minus_base_answer_score']:+.4f}
- Bootstrap 95% CI：[{paired_rag['bootstrap_95_ci'][0]:+.4f}, {paired_rag['bootstrap_95_ci'][1]:+.4f}]

## 解读边界

- 两个Agent会自主生成检索query，因此命中上下文可以不同；这属于Agent能力差异。
- 未调用 `search_knowledge` 的成功回答仍计入工作流成功，但计为RAG路由失败。
- 自动文本指标偏保守，不能替代事实核验；40条固定盲审材料见 `blind_review.jsonl`。
- 无RAG实验使用另一份500条领域数据，不能与本轮200条分数直接相减为RAG净增益。
"""


def build_blind_review(
    results: dict[str, dict[str, dict[str, Any]]],
    *,
    case_ids: list[str],
    models: list[str],
    size: int,
    seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rng = random.Random(seed)
    selected = list(case_ids)
    rng.shuffle(selected)
    selected = selected[:min(size, len(selected))]
    review_rows: list[dict[str, Any]] = []
    key_rows: list[dict[str, Any]] = []
    for index, case_id in enumerate(selected, start=1):
        base, lora = results[models[0]][case_id], results[models[1]][case_id]
        base_is_a = rng.choice([True, False])
        review_id = f"agent-rag-blind-{index:04d}"
        review_rows.append({
            "review_id": review_id,
            "case_id": case_id,
            "question": base["question"],
            "reference_answer": base["reference_answer"],
            "supporting_excerpt": base["supporting_excerpt"],
            "answer_a": base["prediction"] if base_is_a else lora["prediction"],
            "answer_b": lora["prediction"] if base_is_a else base["prediction"],
            "review": {
                "preferred": "",
                "correctness_a_1_to_5": None,
                "correctness_b_1_to_5": None,
                "groundedness_a_1_to_5": None,
                "groundedness_b_1_to_5": None,
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


def write_case_csv(
    path: Path,
    results: dict[str, dict[str, dict[str, Any]]],
    metrics: dict[str, dict[str, dict[str, dict[str, float]]]],
    *,
    case_ids: list[str],
    models: list[str],
) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=[
            "case_id", "question", "source_document",
            "base_status", "lora_status", "base_search_calls", "lora_search_calls",
            "base_source_hit", "lora_source_hit", "base_answer_score", "lora_answer_score",
            "answer_score_delta_lora_minus_base", "base_latency_seconds", "lora_latency_seconds",
        ])
        writer.writeheader()
        for case_id in case_ids:
            base, lora = results[models[0]][case_id], results[models[1]][case_id]
            base_score = metrics[models[0]][case_id]
            lora_score = metrics[models[1]][case_id]
            writer.writerow({
                "case_id": case_id,
                "question": base["question"],
                "source_document": base["source_document"],
                "base_status": base["status"],
                "lora_status": lora["status"],
                "base_search_calls": rag_facts(base)["search_call_count"],
                "lora_search_calls": rag_facts(lora)["search_call_count"],
                "base_source_hit": base_score["retrieval"]["recall_at_5"],
                "lora_source_hit": lora_score["retrieval"]["recall_at_5"],
                "base_answer_score": base_score["answer"]["answer_score"],
                "lora_answer_score": lora_score["answer"]["answer_score"],
                "answer_score_delta_lora_minus_base": (
                    lora_score["answer"]["answer_score"]
                    - base_score["answer"]["answer_score"]
                ),
                "base_latency_seconds": base["latency_seconds"],
                "lora_latency_seconds": lora["latency_seconds"],
            })
    temporary.replace(path)


def tokenize(text: str) -> list[str]:
    """英文按词、中文按单字与双字切分，复用既有RAG指标口径。"""
    tokens: list[str] = []
    for match in TOKEN_PATTERN.findall(text.lower()):
        if re.fullmatch(r"[\u3400-\u9fff]+", match):
            tokens.extend(match)
            tokens.extend(match[index:index + 2] for index in range(len(match) - 1))
        else:
            tokens.append(match)
    return tokens


def multiset_f1(reference: list[str], candidate: list[str]) -> float:
    if not reference or not candidate:
        return 0.0
    left, right = collections.Counter(reference), collections.Counter(candidate)
    overlap = sum((left & right).values())
    precision, recall = overlap / len(candidate), overlap / len(reference)
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def rouge_l_f1(reference: list[str], candidate: list[str]) -> float:
    if not reference or not candidate:
        return 0.0
    previous = [0] * (len(candidate) + 1)
    for left in reference:
        current = [0]
        for index, right in enumerate(candidate, start=1):
            current.append(
                previous[index - 1] + 1
                if left == right else max(current[-1], previous[index])
            )
        previous = current
    lcs = previous[-1]
    precision, recall = lcs / len(candidate), lcs / len(reference)
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def token_recall(reference: list[str], candidate: list[str]) -> float:
    if not reference:
        return 0.0
    left, right = collections.Counter(reference), collections.Counter(candidate)
    return min(1.0, sum((left & right).values()) / sum(left.values()))


def source_domain(source_document: str) -> str:
    match = re.search(r"generated-ragdoc-(\d{2})-", source_document)
    return match.group(1) if match else "unknown"


def rag_facts(record: dict[str, Any]) -> dict[str, Any]:
    """始终从原始工具轨迹重建RAG事实，避免旧结果缓存字段污染报告。"""
    search_calls = [
        call for call in _tool_calls(record)
        if call.get("tool_name") == "search_knowledge"
    ]
    stored = record.get("rag") or {}
    expected_kb = stored.get("expected_knowledge_base_id")
    stored_correct_count = stored.get("correct_knowledge_base_call_count")
    return {
        "search_call_count": len(search_calls),
        "successful_search_call_count": sum(
            search_call_succeeded(call) for call in search_calls
        ),
        "correct_knowledge_base_call_count": (
            int(stored_correct_count)
            if stored_correct_count is not None
            else sum(
                expected_kb is not None
                and int((call.get("arguments") or {}).get("knowledge_base_id") or -1)
                == int(expected_kb)
                for call in search_calls
            )
        ),
        "retrieved_hits": extract_retrieved_hits(search_calls),
    }


def rag_route_passed(record: dict[str, Any]) -> bool:
    facts = rag_facts(record)
    return bool(
        record.get("status") == "success"
        and facts["search_call_count"] == 1
        and facts["successful_search_call_count"] == 1
        and facts["correct_knowledge_base_call_count"] == 1
    )


def _tool_calls(record: dict[str, Any]) -> list[dict[str, Any]]:
    return list((record.get("agent") or {}).get("tool_calls") or [])


def rate(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 0.0


def mean(values: Iterable[float]) -> float:
    items = list(values)
    return round(statistics.mean(items), 6) if items else 0.0


if __name__ == "__main__":
    raise SystemExit(main())
