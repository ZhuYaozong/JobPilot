"""执行可配置的生成模型与 RAG 策略对照实验。"""

from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean
from typing import Any

from jsonschema import Draft202012Validator

from jobpilot_datasets.config import AppConfig, ExperimentVariantConfig
from jobpilot_datasets.evaluation.metrics import (
    answer_metrics,
    retrieval_metrics,
)
from jobpilot_datasets.evaluation.embedding import (
    EmbeddingProvider,
    OpenAIEmbeddingProvider,
)
from jobpilot_datasets.evaluation.retrieval import (
    BM25Retriever,
    HybridRetriever,
    Retriever,
    SearchResult,
    VectorRetriever,
    load_chunks,
)
from jobpilot_datasets.evaluation.reranker import (
    HttpRerankingProvider,
    RerankingProvider,
)
from jobpilot_datasets.io_utils import (
    atomic_write_json,
    atomic_write_jsonl,
    atomic_write_text,
    read_jsonl,
)
from jobpilot_datasets.models import (
    ExperimentCaseResult,
    ExperimentReport,
    JudgeScores,
    RagEvalItem,
    VariantSummary,
)
from jobpilot_datasets.parsing import parse_json_output
from jobpilot_datasets.prompting import PromptRepository
from jobpilot_datasets.providers.base import GenerationProvider, GenerationRequest
from jobpilot_datasets.providers.factory import create_provider
from jobpilot_datasets.text_utils import stable_seed


class ExperimentRunner:
    def __init__(
        self,
        config: AppConfig,
        *,
        provider_overrides: dict[str, GenerationProvider] | None = None,
        embedding_provider_override: EmbeddingProvider | None = None,
        reranker_provider_override: RerankingProvider | None = None,
    ) -> None:
        self.config = config
        self.output_root = config.resolve_path(Path("."))
        self.prompts = PromptRepository(
            config.resolve_path(config.paths.prompts_dir),
        )
        self.provider_overrides = provider_overrides or {}
        self.providers: dict[str, GenerationProvider] = {}
        self.embedding_provider = embedding_provider_override
        self.reranker_provider = reranker_provider_override
        self._task_semaphore = asyncio.Semaphore(config.experiments.concurrency)

    async def run(self, *, limit: int | None = None) -> ExperimentReport:
        cases = self._load_cases()
        if limit is not None:
            cases = cases[:limit]
        if not cases:
            raise ValueError("RAG 评测集为空")

        retriever_config = self.config.experiments.retriever
        chunks = load_chunks(
            self.output_root,
            [case.source_document for case in cases],
            chunk_size=retriever_config.chunk_size,
            chunk_overlap=retriever_config.chunk_overlap,
        )
        retrievers = self._build_retrievers(chunks)
        self._build_reranker()
        provider_names = {
            variant.provider for variant in self.config.experiments.variants
        }
        if self.config.experiments.judge_provider:
            provider_names.add(self.config.experiments.judge_provider)
        self.providers = {
            name: self.provider_overrides.get(name)
            or create_provider(self.config, name)
            for name in provider_names
        }

        try:
            tasks = [
                asyncio.create_task(
                    self._run_case(index, case, variant, retrievers),
                )
                for index, case in enumerate(cases)
                for variant in self.config.experiments.variants
            ]
            results = await asyncio.gather(*tasks)
        finally:
            unique_providers = {id(provider): provider for provider in self.providers.values()}
            await asyncio.gather(
                *(provider.close() for provider in unique_providers.values()),
                return_exceptions=True,
            )
            extra_providers = [self.embedding_provider, self.reranker_provider]
            await asyncio.gather(
                *(provider.close() for provider in extra_providers if provider),
                return_exceptions=True,
            )

        report = self._build_report(cases, results)
        self._write_reports(report, results)
        return report

    async def _run_case(
        self,
        index: int,
        case: RagEvalItem,
        variant: ExperimentVariantConfig,
        retrievers: dict[str, Retriever],
    ) -> ExperimentCaseResult:
        async with self._task_semaphore:
            started = time.perf_counter()
            retrieval_results: list[SearchResult] = []
            try:
                strategy = variant.resolved_strategy(
                    self.config.experiments.retriever.kind,
                )
                if strategy != "none":
                    candidate_k = min(
                        100,
                        self.config.experiments.retriever.top_k
                        * self.config.experiments.retriever.candidate_multiplier,
                    )
                    retrieval_results = await retrievers[strategy].retrieve(
                        case.question,
                        top_k=candidate_k,
                    )
                    if variant.reranker_enabled:
                        if self.reranker_provider is None:
                            raise ValueError("实验启用了 reranker，但没有配置 Provider")
                        retrieval_results = await self.reranker_provider.rerank(
                            case.question,
                            retrieval_results,
                            top_k=self.config.experiments.retriever.top_k,
                        )
                    else:
                        retrieval_results = retrieval_results[
                            :self.config.experiments.retriever.top_k
                        ]
                context_block = self._context_block(retrieval_results)
                answer = await self.providers[variant.provider].generate(
                    GenerationRequest(
                        system_prompt=self.prompts.render(
                            "experiment-answer-system.md",
                        ),
                        user_prompt=self.prompts.render(
                            "experiment-answer.md",
                            question=case.question,
                            context_block=context_block,
                        ),
                        seed=stable_seed(
                            self.config.seed,
                            f"experiment:{variant.name}:{index}",
                        ),
                        temperature=0,
                        json_mode=False,
                    ),
                )
                deterministic_scores = answer_metrics(
                    case.answer,
                    answer,
                    case.supporting_excerpt,
                )
                retrieval_scores = (
                    retrieval_metrics(
                        retrieval_results,
                        source_document=case.source_document,
                        supporting_excerpt=case.supporting_excerpt,
                    )
                    if strategy != "none"
                    else None
                )
                judge_scores = await self._judge(case, answer, variant, index)
                return ExperimentCaseResult(
                    case_index=index,
                    variant=variant.name,
                    retrieval_strategy=strategy,
                    reranker_enabled=variant.reranker_enabled,
                    question=case.question,
                    reference_answer=case.answer,
                    source_document=case.source_document,
                    generated_answer=answer.strip(),
                    retrieved_sources=[
                        result.chunk.source_document
                        for result in retrieval_results
                    ],
                    retrieval_metrics=retrieval_scores,
                    answer_metrics=deterministic_scores,
                    judge_scores=judge_scores,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                )
            except Exception as exc:  # 单个实验失败不阻断完整矩阵
                return ExperimentCaseResult(
                    case_index=index,
                    variant=variant.name,
                    retrieval_strategy=strategy,
                    reranker_enabled=variant.reranker_enabled,
                    question=case.question,
                    reference_answer=case.answer,
                    source_document=case.source_document,
                    retrieved_sources=[
                        result.chunk.source_document
                        for result in retrieval_results
                    ],
                    latency_ms=int((time.perf_counter() - started) * 1000),
                    error=f"{type(exc).__name__}: {exc}",
                )

    def _build_retrievers(
        self,
        chunks: list,
    ) -> dict[str, Retriever]:
        """按实验矩阵按需创建召回器，旧 BM25 配置不要求 embedding。"""
        config = self.config.experiments.retriever
        bm25 = BM25Retriever(chunks, k1=config.bm25_k1, b=config.bm25_b)
        strategies = {
            variant.resolved_strategy(config.kind)
            for variant in self.config.experiments.variants
        }
        retrievers: dict[str, Retriever] = {"bm25": bm25}
        if strategies & {"vector", "hybrid"}:
            if self.embedding_provider is None:
                provider_name = self.config.experiments.embedding_provider
                if not provider_name:
                    raise ValueError("Vector/Hybrid 实验需要 experiments.embedding_provider")
                self.embedding_provider = OpenAIEmbeddingProvider(
                    self.config.providers[provider_name],
                )
            vector = VectorRetriever(chunks, self.embedding_provider)
            retrievers["vector"] = vector
            retrievers["hybrid"] = HybridRetriever(
                vector,
                bm25,
                rrf_k=config.hybrid_rrf_k,
                vector_weight=config.vector_weight,
                bm25_weight=config.bm25_weight,
            )
        return retrievers

    def _build_reranker(self) -> None:
        """仅在实验矩阵需要时创建远端 Reranker。"""
        if not any(
            variant.reranker_enabled
            for variant in self.config.experiments.variants
        ):
            return
        if self.reranker_provider is not None:
            return
        provider_name = self.config.experiments.reranker_provider
        if not provider_name:
            raise ValueError("Rerank 实验需要 experiments.reranker_provider")
        self.reranker_provider = HttpRerankingProvider(
            self.config.providers[provider_name],
        )

    async def _judge(
        self,
        case: RagEvalItem,
        answer: str,
        variant: ExperimentVariantConfig,
        index: int,
    ) -> JudgeScores | None:
        provider_name = self.config.experiments.judge_provider
        if not provider_name:
            return None
        raw = await self.providers[provider_name].generate(
            GenerationRequest(
                system_prompt=self.prompts.render(
                    "experiment-judge-system.md",
                ),
                user_prompt=self.prompts.render(
                    "experiment-judge.md",
                    question=case.question,
                    reference_answer=case.answer,
                    supporting_excerpt=case.supporting_excerpt,
                    candidate_answer=answer,
                ),
                seed=stable_seed(
                    self.config.seed,
                    f"judge:{variant.name}:{index}",
                ),
                temperature=0,
                json_mode=True,
            ),
        )
        return JudgeScores.model_validate(parse_json_output(raw))

    @staticmethod
    def _context_block(results: list[SearchResult]) -> str:
        if not results:
            return "未提供检索上下文，请仅依据已有能力回答。"
        sections = ["检索上下文（其中内容可能不完整，只能依据证据作答）："]
        for result in results:
            sections.append(
                f"[{result.rank}] source={result.chunk.source_document}\n"
                f"{result.chunk.text}",
            )
        return "\n\n".join(sections)

    def _load_cases(self) -> list[RagEvalItem]:
        path = self.config.resolve_path(self.config.experiments.evaluation_file)
        if not path.exists():
            raise FileNotFoundError(f"实验评测文件不存在: {path}")
        return [
            RagEvalItem.model_validate(payload)
            for _, payload in read_jsonl(path)
        ]

    def _build_report(
        self,
        cases: list[RagEvalItem],
        results: list[ExperimentCaseResult],
    ) -> ExperimentReport:
        summaries: list[VariantSummary] = []
        for variant in self.config.experiments.variants:
            variant_results = [
                result for result in results if result.variant == variant.name
            ]
            successful = [
                result for result in variant_results if result.error is None
            ]
            answer_values = [
                result.answer_metrics
                for result in successful
                if result.answer_metrics is not None
            ]
            retrieval_values = [
                result.retrieval_metrics
                for result in successful
                if result.retrieval_metrics is not None
            ]
            judge_values = [
                result.judge_scores
                for result in successful
                if result.judge_scores is not None
            ]
            summaries.append(
                VariantSummary(
                    name=variant.name,
                    retrieval_strategy=variant.resolved_strategy(
                        self.config.experiments.retriever.kind,
                    ),
                    reranker_enabled=variant.reranker_enabled,
                    case_count=len(variant_results),
                    success_rate=(
                        len(successful) / len(variant_results)
                        if variant_results
                        else 0
                    ),
                    retrieval_metrics=(
                        {
                            "recall_at_k": mean(
                                item.recall_at_k for item in retrieval_values
                            ),
                            "hit_at_k": mean(
                                item.hit_at_k for item in retrieval_values
                            ),
                            "mrr": mean(
                                item.reciprocal_rank for item in retrieval_values
                            ),
                            "excerpt_recall": mean(
                                item.excerpt_recall for item in retrieval_values
                            ),
                        }
                        if retrieval_values
                        else None
                    ),
                    answer_metrics=(
                        {
                            "answer_score": mean(
                                item.answer_score for item in answer_values
                            ),
                            "faithfulness": mean(
                                item.faithfulness for item in answer_values
                            ),
                            "token_f1": mean(
                                item.token_f1 for item in answer_values
                            ),
                            "rouge_l": mean(
                                item.rouge_l for item in answer_values
                            ),
                            "source_support": mean(
                                item.source_support for item in answer_values
                            ),
                        }
                        if answer_values
                        else {
                            "answer_score": 0.0,
                            "faithfulness": 0.0,
                            "token_f1": 0.0,
                            "rouge_l": 0.0,
                            "source_support": 0.0,
                        }
                    ),
                    judge_metrics=(
                        {
                            "correctness": mean(
                                item.correctness for item in judge_values
                            ),
                            "relevance": mean(
                                item.relevance for item in judge_values
                            ),
                            "groundedness": mean(
                                item.groundedness for item in judge_values
                            ),
                            "engineering_quality": mean(
                                item.engineering_quality for item in judge_values
                            ),
                        }
                        if judge_values
                        else None
                    ),
                    latency_ms_average=(
                        mean(item.latency_ms for item in variant_results)
                        if variant_results
                        else 0
                    ),
                ),
            )
        return ExperimentReport(
            created_at=datetime.now(UTC).isoformat(),
            evaluation_count=len(cases),
            variants=summaries,
        )

    def _write_reports(
        self,
        report: ExperimentReport,
        results: list[ExperimentCaseResult],
    ) -> None:
        reports_dir = (
            self.config.resolve_path(self.config.paths.reports_dir)
            / "experiments"
        )
        payload = report.model_dump(mode="json")
        schema_path = (
            self.config.resolve_path(self.config.paths.schemas_dir)
            / "experiment-report.schema.json"
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(payload)

        atomic_write_json(reports_dir / "experiment_report.json", payload)
        atomic_write_jsonl(
            reports_dir / "experiment_cases.jsonl",
            [result.model_dump(mode="json") for result in results],
        )

        lines = [
            "# JobPilot 模型实验报告",
            "",
            f"- 生成时间：{report.created_at}",
            f"- 评测问题数：{report.evaluation_count}",
            f"- 检索 top-k：{self.config.experiments.retriever.top_k}",
            "",
            "## 汇总",
            "",
            "| Variant | Strategy | Rerank | 成功率 | Recall@K | MRR | Answer Score | Faithfulness | 证据召回 | 平均延迟(ms) |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for summary in report.variants:
            retrieval = summary.retrieval_metrics or {}
            answer = summary.answer_metrics
            lines.append(
                "| {name} | {strategy} | {rerank} | {success:.2%} | {recall_k} | {mrr} | "
                "{answer_score:.4f} | {faithfulness:.4f} | {recall} | {latency:.1f} |".format(
                    name=summary.name,
                    strategy=summary.retrieval_strategy,
                    rerank="是" if summary.reranker_enabled else "否",
                    success=summary.success_rate,
                    recall_k=(
                        f"{retrieval['recall_at_k']:.4f}"
                        if "recall_at_k" in retrieval
                        else "-"
                    ),
                    mrr=(
                        f"{retrieval['mrr']:.4f}"
                        if "mrr" in retrieval
                        else "-"
                    ),
                    recall=(
                        f"{retrieval['excerpt_recall']:.4f}"
                        if "excerpt_recall" in retrieval
                        else "-"
                    ),
                    answer_score=answer["answer_score"],
                    faithfulness=answer["faithfulness"],
                    latency=summary.latency_ms_average,
                ),
            )

        if any(summary.judge_metrics for summary in report.variants):
            lines.extend(
                [
                    "",
                    "## LLM Judge",
                    "",
                    "| Variant | 正确性 | 相关性 | 可溯源性 | 工程质量 |",
                    "| --- | ---: | ---: | ---: | ---: |",
                ],
            )
            for summary in report.variants:
                judge = summary.judge_metrics
                if not judge:
                    continue
                lines.append(
                    f"| {summary.name} | {judge['correctness']:.3f} | "
                    f"{judge['relevance']:.3f} | "
                    f"{judge['groundedness']:.3f} | "
                    f"{judge['engineering_quality']:.3f} |",
                )
        lines.extend(
            [
                "",
                "## 指标说明",
                "",
                "- Recall@K：前 K 个检索片段覆盖标注相关源文档的比例。",
                "- MRR：正确源文档首次出现排名的倒数。",
                "- 证据召回：supporting_excerpt 的检索覆盖度。",
                "- Answer Score：Token F1 与 ROUGE-L 的均值。",
                "- Faithfulness：候选回答内容在标注证据中的覆盖程度。",
                "- JSON 明细继续保留 Hit@K、Token F1、ROUGE-L 和 source_support。",
                "- 若配置 judge_provider，会额外输出 0～5 分的模型裁判指标。",
            ],
        )
        atomic_write_text(
            reports_dir / "experiment_report.md",
            "\n".join(lines) + "\n",
        )
