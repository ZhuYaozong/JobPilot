"""Base + RAG 与 LoRA + RAG 的同题配对分析。"""

from __future__ import annotations

import math
import random
import re
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

from jobpilot_datasets.io_utils import (
    atomic_write_json,
    atomic_write_jsonl,
    atomic_write_text,
    read_jsonl,
)
from jobpilot_datasets.models import ExperimentCaseResult
from jobpilot_datasets.text_utils import stable_seed


_ANSWER_METRICS = (
    "answer_score",
    "token_f1",
    "rouge_l",
    "faithfulness",
    "source_support",
)
_RETRIEVAL_METRICS = (
    "recall_at_k",
    "hit_at_k",
    "reciprocal_rank",
    "excerpt_recall",
)
_NUMBER_PATTERN = re.compile(
    r"(?P<number>\d+(?:\.\d+)?)\s*"
    r"(?P<unit>%|％|ms|毫秒|s|秒|分钟|小时|天|万|亿|人|次|倍|GB|MB|KB|QPS)?",
    re.IGNORECASE,
)
_SPECULATIVE_MARKERS = (
    "估算",
    "估计",
    "假设为",
    "假定为",
    "行业平均",
    "反推",
)


class RagModelComparison:
    """验证实验控制变量，并生成确定性的配对统计报告。"""

    def __init__(
        self,
        *,
        base_variant: str = "Base + RAG",
        lora_variant: str = "LoRA + RAG",
        bootstrap_samples: int = 5000,
        seed: int = 20260730,
        review_size: int = 40,
    ) -> None:
        if bootstrap_samples <= 0:
            raise ValueError("bootstrap_samples 必须大于 0")
        if review_size < 0:
            raise ValueError("review_size 不能小于 0")
        self.base_variant = base_variant
        self.lora_variant = lora_variant
        self.bootstrap_samples = bootstrap_samples
        self.seed = seed
        self.review_size = review_size

    def run(self, cases_path: Path, output_dir: Path) -> dict[str, Any]:
        """读取逐条实验结果，写出 JSON 和 Markdown 配对报告。"""
        records = [
            ExperimentCaseResult.model_validate(payload)
            for _, payload in read_jsonl(cases_path)
        ]
        report = self.build(records)
        atomic_write_json(output_dir / "comparison_report.json", report)
        atomic_write_text(
            output_dir / "comparison_report.md",
            self._render_markdown(report),
        )
        review_rows, key_rows = self._build_blind_review(records)
        atomic_write_jsonl(output_dir / "blind_review.jsonl", review_rows)
        atomic_write_jsonl(output_dir / "blind_review_key.jsonl", key_rows)
        return report

    def build(
        self,
        records: list[ExperimentCaseResult],
    ) -> dict[str, Any]:
        """从内存记录构建报告，便于单元测试覆盖统计边界。"""
        by_variant: dict[str, dict[int, ExperimentCaseResult]] = defaultdict(dict)
        expected_variants = {self.base_variant, self.lora_variant}
        unexpected = sorted({item.variant for item in records} - expected_variants)
        if unexpected:
            raise ValueError(f"存在未配置的 Variant: {unexpected}")

        for item in records:
            if item.case_index in by_variant[item.variant]:
                raise ValueError(
                    f"Variant {item.variant} 的 case_index {item.case_index} 重复",
                )
            by_variant[item.variant][item.case_index] = item

        base_cases = by_variant[self.base_variant]
        lora_cases = by_variant[self.lora_variant]
        if not base_cases or not lora_cases:
            raise ValueError("Base + RAG 与 LoRA + RAG 都必须存在结果")
        if set(base_cases) != set(lora_cases):
            raise ValueError("两个 Variant 的 case_index 集合不一致")

        pairs: list[tuple[ExperimentCaseResult, ExperimentCaseResult]] = []
        for case_index in sorted(base_cases):
            base = base_cases[case_index]
            lora = lora_cases[case_index]
            self._validate_pair(base, lora)
            pairs.append((base, lora))

        variants = {
            self.base_variant: self._variant_summary([pair[0] for pair in pairs]),
            self.lora_variant: self._variant_summary([pair[1] for pair in pairs]),
        }
        comparisons = {
            metric: self._metric_comparison(pairs, metric)
            for metric in _ANSWER_METRICS
        }
        comparisons["latency_ms"] = self._metric_comparison(
            pairs,
            "latency_ms",
            higher_is_better=False,
        )
        ranked = sorted(
            pairs,
            key=lambda pair: (
                pair[1].answer_metrics.answer_score
                - pair[0].answer_metrics.answer_score,
                -pair[0].case_index,
            ),
            reverse=True,
        )
        return {
            "mode": "paired_rag_model_comparison",
            "base_variant": self.base_variant,
            "lora_variant": self.lora_variant,
            "paired_count": len(pairs),
            "retrieval_alignment": {
                "matched": len(pairs),
                "mismatched": 0,
            },
            "bootstrap": {
                "samples": self.bootstrap_samples,
                "confidence_level": 0.95,
                "seed": self.seed,
            },
            "variants": variants,
            "lora_minus_base": comparisons,
            "largest_improvements": [
                self._case_delta(pair) for pair in ranked[:5]
            ],
            "largest_regressions": [
                self._case_delta(pair) for pair in reversed(ranked[-5:])
            ],
        }

    @staticmethod
    def _validate_pair(
        base: ExperimentCaseResult,
        lora: ExperimentCaseResult,
    ) -> None:
        for item in (base, lora):
            if item.error is not None:
                raise ValueError(
                    f"{item.variant} case {item.case_index} 失败: {item.error}",
                )
            if item.retrieval_strategy != "hybrid" or not item.reranker_enabled:
                raise ValueError(
                    f"{item.variant} case {item.case_index} 不是 Hybrid + Rerank",
                )
            if item.answer_metrics is None or item.retrieval_metrics is None:
                raise ValueError(
                    f"{item.variant} case {item.case_index} 缺少评测指标",
                )
        if (
            base.question != lora.question
            or base.reference_answer != lora.reference_answer
            or base.source_document != lora.source_document
        ):
            raise ValueError(f"case {base.case_index} 的题目或黄金答案不一致")
        if (
            base.retrieved_sources != lora.retrieved_sources
            or base.retrieval_metrics != lora.retrieval_metrics
        ):
            raise ValueError(f"case {base.case_index} 的检索上下文不一致")

    @staticmethod
    def _variant_summary(
        cases: list[ExperimentCaseResult],
    ) -> dict[str, Any]:
        answer = {
            metric: mean(
                getattr(item.answer_metrics, metric)
                for item in cases
                if item.answer_metrics is not None
            )
            for metric in _ANSWER_METRICS
        }
        retrieval = {
            metric: mean(
                getattr(item.retrieval_metrics, metric)
                for item in cases
                if item.retrieval_metrics is not None
            )
            for metric in _RETRIEVAL_METRICS
        }
        latencies = [item.latency_ms for item in cases]
        answer_lengths = [len(item.generated_answer) for item in cases]
        novel_numeric_cases = [
            item for item in cases if _reference_novel_numeric_claims(item)
        ]
        speculative_numeric_cases = [
            item
            for item in novel_numeric_cases
            if any(marker in item.generated_answer for marker in _SPECULATIVE_MARKERS)
        ]
        return {
            "case_count": len(cases),
            "answer_metrics": answer,
            "retrieval_metrics": retrieval,
            "latency_ms_average": mean(latencies),
            "latency_ms_p95": _nearest_rank_percentile(latencies, 0.95),
            "answer_length_chars_average": mean(answer_lengths),
            "answer_length_chars_p50": _percentile(answer_lengths, 0.50),
            "answer_length_chars_p95": _nearest_rank_percentile(
                answer_lengths,
                0.95,
            ),
            # 只表示数字未出现在问题或参考答案中，不直接等价于事实错误。
            "reference_novel_numeric_claim_samples": len(novel_numeric_cases),
            "reference_novel_numeric_claim_rate": (
                len(novel_numeric_cases) / len(cases)
            ),
            "speculative_numeric_risk_samples": len(speculative_numeric_cases),
            "speculative_numeric_risk_rate": (
                len(speculative_numeric_cases) / len(cases)
            ),
        }

    def _metric_comparison(
        self,
        pairs: list[tuple[ExperimentCaseResult, ExperimentCaseResult]],
        metric: str,
        *,
        higher_is_better: bool = True,
    ) -> dict[str, Any]:
        deltas = [
            self._metric_value(lora, metric) - self._metric_value(base, metric)
            for base, lora in pairs
        ]
        tolerance = 1e-12
        wins = sum(
            delta > tolerance if higher_is_better else delta < -tolerance
            for delta in deltas
        )
        losses = sum(
            delta < -tolerance if higher_is_better else delta > tolerance
            for delta in deltas
        )
        lower, upper = self._bootstrap_interval(deltas, metric)
        return {
            "mean_delta": mean(deltas),
            "ci95_lower": lower,
            "ci95_upper": upper,
            "wins": wins,
            "ties": len(deltas) - wins - losses,
            "losses": losses,
        }

    def _build_blind_review(
        self,
        records: list[ExperimentCaseResult],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """确定性抽样并随机隐藏模型身份，供后续人工语义复核。"""
        grouped: dict[int, dict[str, ExperimentCaseResult]] = defaultdict(dict)
        for item in records:
            grouped[item.case_index][item.variant] = item
        eligible = sorted(
            index
            for index, variants in grouped.items()
            if self.base_variant in variants and self.lora_variant in variants
        )
        generator = random.Random(stable_seed(self.seed, "blind-review"))
        generator.shuffle(eligible)
        selected = eligible[: min(self.review_size, len(eligible))]
        review_rows: list[dict[str, Any]] = []
        key_rows: list[dict[str, Any]] = []
        for review_index, case_index in enumerate(selected, start=1):
            base = grouped[case_index][self.base_variant]
            lora = grouped[case_index][self.lora_variant]
            base_is_a = bool(generator.getrandbits(1))
            review_id = f"rag-blind-{review_index:04d}"
            answer_a = base.generated_answer if base_is_a else lora.generated_answer
            answer_b = lora.generated_answer if base_is_a else base.generated_answer
            review_rows.append(
                {
                    "review_id": review_id,
                    "question": base.question,
                    "reference_answer": base.reference_answer,
                    "source_document": base.source_document,
                    "answer_a": answer_a,
                    "answer_b": answer_b,
                    "preferred": "",
                    "reason": "",
                },
            )
            key_rows.append(
                {
                    "review_id": review_id,
                    "answer_a_variant": (
                        self.base_variant if base_is_a else self.lora_variant
                    ),
                    "answer_b_variant": (
                        self.lora_variant if base_is_a else self.base_variant
                    ),
                    "case_index": case_index,
                },
            )
        return review_rows, key_rows

    @staticmethod
    def _metric_value(item: ExperimentCaseResult, metric: str) -> float:
        if metric == "latency_ms":
            return float(item.latency_ms)
        if item.answer_metrics is None:
            raise ValueError(f"case {item.case_index} 缺少 answer_metrics")
        return float(getattr(item.answer_metrics, metric))

    def _bootstrap_interval(
        self,
        deltas: list[float],
        metric: str,
    ) -> tuple[float, float]:
        # 每个指标使用独立确定性随机流，保证调整字段顺序不会改变置信区间。
        generator = random.Random(stable_seed(self.seed, metric))
        sample_size = len(deltas)
        estimates = sorted(
            mean(deltas[generator.randrange(sample_size)] for _ in range(sample_size))
            for _ in range(self.bootstrap_samples)
        )
        return _percentile(estimates, 0.025), _percentile(estimates, 0.975)

    @staticmethod
    def _case_delta(
        pair: tuple[ExperimentCaseResult, ExperimentCaseResult],
    ) -> dict[str, Any]:
        base, lora = pair
        if base.answer_metrics is None or lora.answer_metrics is None:
            raise ValueError(f"case {base.case_index} 缺少 answer_metrics")
        return {
            "case_index": base.case_index,
            "question": base.question,
            "source_document": base.source_document,
            "answer_score_delta": (
                lora.answer_metrics.answer_score
                - base.answer_metrics.answer_score
            ),
            "base_answer": base.generated_answer,
            "lora_answer": lora.generated_answer,
        }

    @staticmethod
    def _render_markdown(report: dict[str, Any]) -> str:
        variants = report["variants"]
        base = variants[report["base_variant"]]
        lora = variants[report["lora_variant"]]
        comparisons = report["lora_minus_base"]
        lines = [
            "# Base + RAG / LoRA + RAG 配对评测",
            "",
            f"- 配对问题数：{report['paired_count']}",
            "- 检索策略：Hybrid + Rerank",
            f"- 检索上下文一致：{report['retrieval_alignment']['matched']} / {report['paired_count']}",
            f"- Bootstrap：{report['bootstrap']['samples']} 次，95% 置信区间",
            "",
            "## 汇总",
            "",
            "| 指标 | Base + RAG | LoRA + RAG | LoRA - Base | 95% CI | 胜/平/负 |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
        labels = {
            "answer_score": "Answer Score",
            "token_f1": "Token F1",
            "rouge_l": "ROUGE-L",
            "faithfulness": "Faithfulness",
            "source_support": "Source Support",
        }
        for metric, label in labels.items():
            comparison = comparisons[metric]
            lines.append(
                f"| {label} | {base['answer_metrics'][metric]:.4f} | "
                f"{lora['answer_metrics'][metric]:.4f} | "
                f"{comparison['mean_delta']:+.4f} | "
                f"[{comparison['ci95_lower']:+.4f}, {comparison['ci95_upper']:+.4f}] | "
                f"{comparison['wins']}/{comparison['ties']}/{comparison['losses']} |",
            )
        latency = comparisons["latency_ms"]
        lines.append(
            f"| 平均延迟(ms) | {base['latency_ms_average']:.1f} | "
            f"{lora['latency_ms_average']:.1f} | {latency['mean_delta']:+.1f} | "
            f"[{latency['ci95_lower']:+.1f}, {latency['ci95_upper']:+.1f}] | "
            f"{latency['wins']}/{latency['ties']}/{latency['losses']} |",
        )
        lines.extend(
            [
                "",
                "## 输出诊断",
                "",
                "| Variant | 平均字符 | P50字符 | P95字符 | 新增数字声明率 | 推测性数字风险率 |",
                "| --- | ---: | ---: | ---: | ---: | ---: |",
                f"| {report['base_variant']} | {base['answer_length_chars_average']:.1f} | "
                f"{base['answer_length_chars_p50']:.1f} | {base['answer_length_chars_p95']:.1f} | "
                f"{base['reference_novel_numeric_claim_rate']:.2%} | "
                f"{base['speculative_numeric_risk_rate']:.2%} |",
                f"| {report['lora_variant']} | {lora['answer_length_chars_average']:.1f} | "
                f"{lora['answer_length_chars_p50']:.1f} | {lora['answer_length_chars_p95']:.1f} | "
                f"{lora['reference_novel_numeric_claim_rate']:.2%} | "
                f"{lora['speculative_numeric_risk_rate']:.2%} |",
                "",
                "## 检索指标",
                "",
                "两组使用完全一致的检索上下文，因此只展示一次共同检索质量：",
                "",
                f"- Recall@5：{base['retrieval_metrics']['recall_at_k']:.4f}",
                f"- MRR：{base['retrieval_metrics']['reciprocal_rank']:.4f}",
                f"- Evidence Recall：{base['retrieval_metrics']['excerpt_recall']:.4f}",
                "",
                "## 解读边界",
                "",
                "- 置信区间完全大于 0 表示 LoRA + RAG 有稳定优势；完全小于 0 表示 Base + RAG 有稳定优势。",
                "- 延迟差值为 LoRA + RAG 减 Base + RAG；负值表示 LoRA 更快。",
                "- 新增数字声明只表示数字未出现在题目或参考答案中，是风险筛查而非事实错误定论。",
                "- 自动词面指标不能替代人工语义盲评，典型样本保存在 JSON 报告中。",
                "",
            ],
        )
        return "\n".join(lines)


def _percentile(values: list[float] | list[int], quantile: float) -> float:
    """使用线性插值计算分位数，输入必须非空。"""
    if not values:
        raise ValueError("分位数输入不能为空")
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def _numeric_claims(text: str) -> set[str]:
    """忽略 1～10 的裸序号，提取带单位或较大的数字声明。"""
    claims: set[str] = set()
    for match in _NUMBER_PATTERN.finditer(text):
        number = match.group("number")
        unit = (match.group("unit") or "").lower()
        if not unit and float(number) <= 10:
            continue
        claims.add(f"{number}{unit}")
    return claims


def _nearest_rank_percentile(
    values: list[float] | list[int],
    quantile: float,
) -> float:
    """与主实验报告保持一致，使用 nearest-rank 计算 P95。"""
    if not values:
        raise ValueError("分位数输入不能为空")
    ordered = sorted(float(value) for value in values)
    rank = max(1, math.ceil(len(ordered) * quantile))
    return ordered[rank - 1]


def _reference_novel_numeric_claims(item: ExperimentCaseResult) -> set[str]:
    reference_claims = _numeric_claims(
        f"{item.question}\n{item.reference_answer}",
    )
    return _numeric_claims(item.generated_answer) - reference_claims
