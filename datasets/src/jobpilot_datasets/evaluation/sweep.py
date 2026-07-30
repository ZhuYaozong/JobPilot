"""Hybrid + Rerank 检索参数的确定性调参与隔离验证。"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jobpilot_datasets.config import AppConfig, ExperimentVariantConfig
from jobpilot_datasets.evaluation.runner import ExperimentRunner
from jobpilot_datasets.io_utils import (
    atomic_write_json,
    atomic_write_text,
    read_jsonl,
)
from jobpilot_datasets.models import RagEvalItem, VariantSummary
from jobpilot_datasets.text_utils import sha256_text, stable_seed


@dataclass(frozen=True, slots=True)
class HybridSweepCandidate:
    """一次 Hybrid + Rerank 参数组合。"""

    vector_weight: float
    bm25_weight: float
    rrf_k: int
    candidate_multiplier: int

    @property
    def slug(self) -> str:
        """生成只含安全字符的报告目录名。"""
        vector = f"{self.vector_weight:g}".replace(".", "p")
        bm25 = f"{self.bm25_weight:g}".replace(".", "p")
        return (
            f"vw-{vector}_bw-{bm25}_rrf-{self.rrf_k}_"
            f"cm-{self.candidate_multiplier}"
        )

    def as_dict(self) -> dict[str, float | int | str]:
        return {
            "slug": self.slug,
            "vector_weight": self.vector_weight,
            "bm25_weight": self.bm25_weight,
            "rrf_k": self.rrf_k,
            "candidate_multiplier": self.candidate_multiplier,
        }


RunnerFactory = Callable[[AppConfig, Path], ExperimentRunner]


class RetrievalSweepRunner:
    """先在每篇文档一条问题上调参，再用其余问题做隔离验证。"""

    BASELINE = HybridSweepCandidate(1.0, 1.0, 60, 3)
    VECTOR_WEIGHTS = (0.25, 0.5, 1.0, 2.0)
    RRF_VALUES = (10, 30, 60)
    CANDIDATE_MULTIPLIERS = (2, 3, 5)
    VALIDATION_TOP_N = 3

    def __init__(
        self,
        config: AppConfig,
        *,
        runner_factory: RunnerFactory | None = None,
        progress: Callable[[str], None] | None = None,
    ) -> None:
        self.config = config
        self.runner_factory = runner_factory or self._default_runner_factory
        self.progress = progress or (lambda message: print(message, flush=True))

    async def run(self) -> dict[str, Any]:
        cases, dataset_path = self._load_cases()
        tuning_indices, validation_indices = self.build_stratified_split(
            cases,
            seed=self.config.seed,
        )

        tuning_results: dict[str, dict[str, Any]] = {}
        stage_one_candidates = [
            HybridSweepCandidate(weight, 1.0, rrf_k, 3)
            for weight in self.VECTOR_WEIGHTS
            for rrf_k in self.RRF_VALUES
        ]
        for index, candidate in enumerate(stage_one_candidates, start=1):
            self.progress(
                f"调参阶段 1/2 [{index}/{len(stage_one_candidates)}] "
                f"{candidate.slug}",
            )
            tuning_results[candidate.slug] = await self._evaluate_candidate(
                candidate,
                tuning_indices,
                phase="tuning-stage-1",
            )

        best_stage_one = self._rank_results(tuning_results.values())[0]
        best_candidate = self._candidate_from_result(best_stage_one)
        stage_two_candidates = [
            HybridSweepCandidate(
                best_candidate.vector_weight,
                best_candidate.bm25_weight,
                best_candidate.rrf_k,
                multiplier,
            )
            for multiplier in self.CANDIDATE_MULTIPLIERS
        ]
        pending_stage_two = [
            candidate
            for candidate in stage_two_candidates
            if candidate.slug not in tuning_results
        ]
        for index, candidate in enumerate(pending_stage_two, start=1):
            self.progress(
                f"调参阶段 2/2 [{index}/{len(pending_stage_two)}] "
                f"{candidate.slug}",
            )
            tuning_results[candidate.slug] = await self._evaluate_candidate(
                candidate,
                tuning_indices,
                phase="tuning-stage-2",
            )

        ranked_tuning = self._rank_results(tuning_results.values())
        validation_candidates = [
            self._candidate_from_result(result)
            for result in ranked_tuning[: self.VALIDATION_TOP_N]
        ]
        if self.BASELINE not in validation_candidates:
            validation_candidates.append(self.BASELINE)

        validation_results: list[dict[str, Any]] = []
        for index, candidate in enumerate(validation_candidates, start=1):
            self.progress(
                f"隔离验证 [{index}/{len(validation_candidates)}] "
                f"{candidate.slug}",
            )
            validation_results.append(
                await self._evaluate_candidate(
                    candidate,
                    validation_indices,
                    phase="validation",
                ),
            )

        ranked_validation = self._rank_results(validation_results)
        winner = ranked_validation[0]
        baseline = next(
            result
            for result in validation_results
            if result["slug"] == self.BASELINE.slug
        )
        report = {
            "created_at": datetime.now(UTC).isoformat(),
            "mode": "retrieval_parameter_sweep",
            "dataset_path": str(dataset_path),
            "dataset_sha256": sha256_text(
                dataset_path.read_text(encoding="utf-8"),
            ),
            "case_count": len(cases),
            "corpus_document_count": len(
                {case.source_document for case in cases},
            ),
            "tuning_case_count": len(tuning_indices),
            "validation_case_count": len(validation_indices),
            "tuning_case_indices": tuning_indices,
            "validation_case_indices": validation_indices,
            "selection_rule": (
                "quality_score=0.45*MRR+0.35*EvidenceRecall+0.20*Recall@5；"
                "同分时依次比较 MRR、Evidence Recall、Recall@5 和平均延迟"
            ),
            "baseline_candidate": self.BASELINE.as_dict(),
            "tuning_results": ranked_tuning,
            "validation_results": ranked_validation,
            "winner": winner,
            "baseline_validation": baseline,
            "winner_delta_vs_baseline": {
                "recall_at_k": winner["recall_at_k"]
                - baseline["recall_at_k"],
                "mrr": winner["mrr"] - baseline["mrr"],
                "excerpt_recall": winner["excerpt_recall"]
                - baseline["excerpt_recall"],
                "latency_ms_average": winner["latency_ms_average"]
                - baseline["latency_ms_average"],
            },
        }
        self._write_report(report)
        return report

    async def _evaluate_candidate(
        self,
        candidate: HybridSweepCandidate,
        case_indices: list[int],
        *,
        phase: str,
    ) -> dict[str, Any]:
        config = self.config.model_copy(deep=True)
        retriever = config.experiments.retriever
        retriever.vector_weight = candidate.vector_weight
        retriever.bm25_weight = candidate.bm25_weight
        retriever.hybrid_rrf_k = candidate.rrf_k
        retriever.candidate_multiplier = candidate.candidate_multiplier
        config.experiments.variants = [
            ExperimentVariantConfig(
                name="Hybrid + Rerank Sweep",
                provider="base",
                retrieval_strategy="hybrid",
                reranker_enabled=True,
            ),
        ]

        report_subdir = (
            Path("retrieval-sweep") / "runs" / phase / candidate.slug
        )
        experiment = await self.runner_factory(
            config,
            report_subdir,
        ).run(
            case_indices=case_indices,
            retrieval_only=True,
        )
        summary = experiment.variants[0]
        if summary.success_rate != 1.0:
            raise RuntimeError(
                f"参数组合存在失败 case: {candidate.slug}, "
                f"success_rate={summary.success_rate}",
            )
        return self._result_payload(candidate, summary, phase)

    @staticmethod
    def _result_payload(
        candidate: HybridSweepCandidate,
        summary: VariantSummary,
        phase: str,
    ) -> dict[str, Any]:
        metrics = summary.retrieval_metrics
        if metrics is None:
            raise RuntimeError(f"参数组合缺少检索指标: {candidate.slug}")
        recall = metrics["recall_at_k"]
        mrr = metrics["mrr"]
        evidence = metrics["excerpt_recall"]
        payload: dict[str, Any] = {
            **candidate.as_dict(),
            "phase": phase,
            "case_count": summary.case_count,
            "success_rate": summary.success_rate,
            "recall_at_k": recall,
            "mrr": mrr,
            "excerpt_recall": evidence,
            "latency_ms_average": summary.latency_ms_average,
            "latency_ms_p95": summary.latency_ms_p95,
            "quality_score": 0.45 * mrr + 0.35 * evidence + 0.20 * recall,
        }
        return payload

    @staticmethod
    def _rank_results(
        results: Any,
    ) -> list[dict[str, Any]]:
        return sorted(
            results,
            key=lambda item: (
                -item["quality_score"],
                -item["mrr"],
                -item["excerpt_recall"],
                -item["recall_at_k"],
                item["latency_ms_average"],
                item["slug"],
            ),
        )

    @staticmethod
    def _candidate_from_result(
        result: dict[str, Any],
    ) -> HybridSweepCandidate:
        return HybridSweepCandidate(
            vector_weight=float(result["vector_weight"]),
            bm25_weight=float(result["bm25_weight"]),
            rrf_k=int(result["rrf_k"]),
            candidate_multiplier=int(result["candidate_multiplier"]),
        )

    @staticmethod
    def build_stratified_split(
        cases: list[RagEvalItem],
        *,
        seed: int,
    ) -> tuple[list[int], list[int]]:
        """每篇文档确定性抽一条调参，其余全部留作验证。"""
        grouped: dict[str, list[int]] = defaultdict(list)
        for index, case in enumerate(cases):
            grouped[case.source_document].append(index)

        tuning: list[int] = []
        for source_document, indices in sorted(grouped.items()):
            selected = stable_seed(seed, f"retrieval-sweep:{source_document}")
            tuning.append(indices[selected % len(indices)])
        tuning_set = set(tuning)
        validation = [
            index for index in range(len(cases)) if index not in tuning_set
        ]
        if not validation:
            raise ValueError("参数扫描至少需要一条独立验证问题")
        return sorted(tuning), validation

    def _load_cases(self) -> tuple[list[RagEvalItem], Path]:
        path = self.config.resolve_path(self.config.experiments.evaluation_file)
        if not path.exists():
            raise FileNotFoundError(f"实验评测文件不存在: {path}")
        cases = [
            RagEvalItem.model_validate(payload)
            for _, payload in read_jsonl(path)
        ]
        if not cases:
            raise ValueError("RAG 评测集为空")
        return cases, path

    def _write_report(self, report: dict[str, Any]) -> None:
        output_dir = (
            self.config.resolve_path(self.config.paths.reports_dir)
            / "retrieval-sweep"
        )
        atomic_write_json(output_dir / "retrieval_sweep_report.json", report)

        lines = [
            "# JobPilot Hybrid 参数扫描报告",
            "",
            f"- 生成时间：{report['created_at']}",
            f"- 总问题数：{report['case_count']}",
            f"- 调参集：{report['tuning_case_count']} 条",
            f"- 隔离验证集：{report['validation_case_count']} 条",
            f"- 语料文档数：{report['corpus_document_count']}",
            "",
            "## 隔离验证结果",
            "",
            "| 排名 | 参数 | Recall@5 | MRR | Evidence Recall | 平均延迟(ms) | P95(ms) | 综合分 |",
            "| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for rank, result in enumerate(report["validation_results"], start=1):
            lines.append(
                "| {rank} | {slug} | {recall:.4f} | {mrr:.4f} | "
                "{evidence:.4f} | {latency:.1f} | {p95:.1f} | {score:.6f} |".format(
                    rank=rank,
                    slug=result["slug"],
                    recall=result["recall_at_k"],
                    mrr=result["mrr"],
                    evidence=result["excerpt_recall"],
                    latency=result["latency_ms_average"],
                    p95=result["latency_ms_p95"],
                    score=result["quality_score"],
                ),
            )

        winner = report["winner"]
        delta = report["winner_delta_vs_baseline"]
        lines.extend(
            [
                "",
                "## 推荐",
                "",
                f"- 最优参数：`{winner['slug']}`。",
                f"- 相对当前基线 MRR 变化：{delta['mrr']:+.4f}。",
                f"- 相对当前基线 Evidence Recall 变化：{delta['excerpt_recall']:+.4f}。",
                f"- 相对当前基线平均延迟变化：{delta['latency_ms_average']:+.1f} ms。",
                "- 参数只在 50 条调参集上选择，最终排名来自其余 150 条隔离验证集。",
            ],
        )
        atomic_write_text(
            output_dir / "retrieval_sweep_report.md",
            "\n".join(lines) + "\n",
        )

    @staticmethod
    def _default_runner_factory(
        config: AppConfig,
        report_subdir: Path,
    ) -> ExperimentRunner:
        return ExperimentRunner(config, report_subdir=report_subdir)
