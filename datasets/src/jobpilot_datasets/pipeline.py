"""SFT、RAG 文档和 RAG 评测数据生成流水线。"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

from jobpilot_datasets.checkpoint import CheckpointStore
from jobpilot_datasets.config import AppConfig
from jobpilot_datasets.deduplication import QuestionDeduplicator
from jobpilot_datasets.io_utils import atomic_write_jsonl, atomic_write_text
from jobpilot_datasets.models import (
    AcceptedRecord,
    DocumentManifestItem,
    PlanItem,
    RagDocumentCandidate,
    RagEvalCandidate,
    RagEvalItem,
    RejectedRecord,
    SFTCandidate,
    SFTItem,
)
from jobpilot_datasets.parsing import (
    ModelOutputParseError,
    extract_items,
    parse_json_output,
)
from jobpilot_datasets.planning import (
    build_lora_evaluation_plan,
    build_rag_document_plan,
    build_rag_evaluation_plan,
    build_sft_plan,
)
from jobpilot_datasets.prompting import PromptRepository
from jobpilot_datasets.providers.base import GenerationProvider, GenerationRequest
from jobpilot_datasets.sources import selected_document_manifests
from jobpilot_datasets.text_utils import (
    ensure_within,
    safe_filename,
    sha256_text,
    stable_seed,
)
from jobpilot_datasets.validation import (
    validate_rag_document,
    validate_rag_eval_item,
    validate_sft_item,
)


class GenerationIncompleteError(RuntimeError):
    """达到最大重试次数后仍有任务未通过质量门禁。"""


@dataclass(frozen=True, slots=True)
class StageResult:
    stage: str
    planned: int
    accepted: int
    completed: bool
    output_files: tuple[str, ...]


class DatasetPipeline:
    """统一管理计划、生成、校验、去重、checkpoint 和最终导出。"""

    def __init__(
        self,
        config: AppConfig,
        provider: GenerationProvider,
        *,
        resume: bool,
        progress: Callable[[str], None] | None = None,
    ) -> None:
        self.config = config
        self.provider = provider
        self.progress = progress or (lambda _: None)
        self.output_root = config.resolve_path(Path("."))
        self.prompts = PromptRepository(
            config.resolve_path(config.paths.prompts_dir),
        )
        self.checkpoint = CheckpointStore(
            config.resolve_path(config.paths.work_dir),
            config_fingerprint=config.fingerprint,
            seed=config.seed,
            resume=resume,
        )
        provider_config = config.providers[config.generation.provider]
        self.checkpoint.set_run_metadata(
            {
                "provider_ref": config.generation.provider,
                "provider_kind": provider_config.kind,
                "model": provider_config.model,
                "base_url": provider_config.base_url,
            },
        )
        self._last_usage_snapshot: dict[str, int] = {}

    @property
    def _generation_concurrency(self) -> int:
        """返回 Provider 实际采用的运行时并发数。"""
        configured = self.config.providers[
            self.config.generation.provider
        ].concurrency
        return int(getattr(self.provider, "concurrency", configured))

    async def generate_sft(self, *, limit: int | None = None) -> StageResult:
        return await self._generate_sft_like(
            stage="sft",
            all_plans=build_sft_plan(self.config),
            batch_size=self.config.generation.batch_size,
            system_prompt_name="sft-system.md",
            limit=limit,
        )

    async def generate_lora_evaluation(
        self,
        *,
        limit: int | None = None,
    ) -> StageResult:
        return await self._generate_sft_like(
            stage="lora_evaluation",
            all_plans=build_lora_evaluation_plan(self.config),
            batch_size=self.config.lora_evaluation.batch_size,
            system_prompt_name="lora-eval-system.md",
            limit=limit,
        )

    async def _generate_sft_like(
        self,
        *,
        stage: str,
        all_plans: list[PlanItem],
        batch_size: int,
        system_prompt_name: str,
        limit: int | None,
    ) -> StageResult:
        self.checkpoint.ensure_plan(stage, all_plans)
        self.checkpoint.mark_started(stage)
        selected = all_plans[:limit] if limit is not None else all_plans
        accepted = self.checkpoint.load_accepted(stage)
        attempts = self.checkpoint.rejection_attempts(stage)
        deduplicator = QuestionDeduplicator(self.config.deduplication)

        seed_records: list[AcceptedRecord] = []
        if stage == "lora_evaluation":
            sft_records = self.checkpoint.load_accepted("sft")
            expected_sft = sum(self.config.lora.splits.values())
            if len(sft_records) != expected_sft:
                raise GenerationIncompleteError(
                    "生成 LoRA evaluation 前必须先完整生成 SFT "
                    f"({len(sft_records)}/{expected_sft})",
                )
            seed_records.extend(sft_records.values())
        seed_records.extend(accepted.values())

        for record in sorted(
            seed_records,
            key=lambda item: item.plan.ordinal,
        ):
            item = SFTItem.model_validate(record.data)
            match = deduplicator.add(
                record.plan.plan_id,
                f"{item.instruction}\n{item.input}",
            )
            if match is not None:
                raise GenerationIncompleteError(
                    f"SFT 类数据中存在重复问题: {record.plan.plan_id} / "
                    f"{match.existing_id}",
                )

        pending = [
            plan
            for plan in selected
            if plan.plan_id not in accepted
            and attempts.get(plan.plan_id, 0)
            < self.config.generation.max_attempts_per_item
        ]
        while pending:
            wave = pending[
                : batch_size
                * self._generation_concurrency
            ]
            batches = [
                wave[index : index + batch_size]
                for index in range(0, len(wave), batch_size)
            ]
            raw_responses = await asyncio.gather(
                *(
                    self._request_sft_batch(
                        batch,
                        attempts,
                        stage=stage,
                        system_prompt_name=system_prompt_name,
                    )
                    for batch in batches
                ),
            )
            for batch, raw in zip(batches, raw_responses, strict=True):
                candidates, parse_error = self._parse_candidates(
                    batch,
                    raw,
                    SFTCandidate,
                )
                if parse_error is not None:
                    self._reject_batch_parse_error(
                        batch,
                        attempts,
                        parse_error,
                        raw,
                    )
                    continue
                by_plan = {
                    candidate.plan_id: candidate
                    for candidate in candidates
                }
                for plan in batch:
                    candidate = by_plan.get(plan.plan_id)
                    attempt = attempts.get(plan.plan_id, 0) + 1
                    if candidate is None:
                        self._reject(
                            plan,
                            attempt,
                            ["模型响应缺少该 plan_id"],
                            raw,
                        )
                        attempts[plan.plan_id] = attempt
                        continue
                    item = SFTItem(
                        instruction=candidate.instruction,
                        input=candidate.input,
                        output=candidate.output,
                    )
                    errors = validate_sft_item(item, self.config)
                    duplicate = deduplicator.check(
                        f"{item.instruction}\n{item.input}",
                    )
                    if duplicate is not None:
                        errors.append(
                            f"问题与 {duplicate.existing_id} "
                            f"{duplicate.kind} 重复，相似度 "
                            f"{duplicate.similarity:.1f}",
                        )
                    if errors:
                        self._reject(plan, attempt, errors, raw)
                        attempts[plan.plan_id] = attempt
                        continue

                    deduplicator.add(
                        plan.plan_id,
                        f"{item.instruction}\n{item.input}",
                    )
                    record = AcceptedRecord(
                        plan=plan,
                        data=item.model_dump(mode="json"),
                    )
                    self.checkpoint.append_accepted(stage, record)
                    accepted[plan.plan_id] = record
                    attempts[plan.plan_id] = attempt

            self.progress(
                f"{stage} checkpoint: {len(accepted)}/{len(all_plans)}",
            )
            pending = [
                plan
                for plan in selected
                if plan.plan_id not in accepted
                and attempts.get(plan.plan_id, 0)
                < self.config.generation.max_attempts_per_item
            ]

        exhausted = [
            plan.plan_id
            for plan in selected
            if plan.plan_id not in accepted
        ]
        if exhausted:
            raise GenerationIncompleteError(
                f"{stage} 有 {len(exhausted)} 条达到最大重试次数，示例: "
                + ", ".join(exhausted[:5]),
            )

        complete = all(plan.plan_id in accepted for plan in all_plans)
        outputs: tuple[str, ...] = ()
        if complete:
            if stage == "sft":
                outputs = self._export_sft(all_plans, accepted)
            else:
                outputs = self._export_lora_evaluation(all_plans, accepted)
            self.checkpoint.mark_complete(stage, len(all_plans))
        return StageResult(
            stage=stage,
            planned=len(selected),
            accepted=sum(plan.plan_id in accepted for plan in selected),
            completed=complete,
            output_files=outputs,
        )

    async def generate_rag_documents(
        self,
        *,
        limit: int | None = None,
    ) -> StageResult:
        all_plans = build_rag_document_plan(self.config)
        self.checkpoint.ensure_plan("rag_documents", all_plans)
        self.checkpoint.mark_started("rag_documents")
        selected = all_plans[:limit] if limit is not None else all_plans
        accepted = self.checkpoint.load_accepted("rag_documents")
        attempts = self.checkpoint.rejection_attempts("rag_documents")
        deduplicator = QuestionDeduplicator(self.config.deduplication)
        for record in sorted(
            accepted.values(),
            key=lambda item: item.plan.ordinal,
        ):
            match = deduplicator.add(
                record.plan.plan_id,
                str(record.data["markdown"]),
            )
            if match is not None:
                raise GenerationIncompleteError(
                    "RAG 文档 checkpoint 中存在重复内容: "
                    f"{record.plan.plan_id} / {match.existing_id}",
                )

        pending = [
            plan
            for plan in selected
            if plan.plan_id not in accepted
            and attempts.get(plan.plan_id, 0)
            < self.config.generation.max_attempts_per_item
        ]
        while pending:
            concurrency = self._generation_concurrency
            wave = pending[
                : self.config.rag_documents.batch_size * concurrency
            ]
            batches = [
                wave[index : index + self.config.rag_documents.batch_size]
                for index in range(
                    0,
                    len(wave),
                    self.config.rag_documents.batch_size,
                )
            ]
            raw_responses = await asyncio.gather(
                *(
                    self._request_rag_document_batch(batch, attempts)
                    for batch in batches
                ),
            )
            for batch, raw in zip(batches, raw_responses, strict=True):
                candidates, parse_error = self._parse_candidates(
                    batch,
                    raw,
                    RagDocumentCandidate,
                )
                if parse_error is not None:
                    self._reject_batch_parse_error(
                        batch,
                        attempts,
                        parse_error,
                        raw,
                    )
                    continue
                by_plan = {
                    candidate.plan_id: candidate
                    for candidate in candidates
                }
                for plan in batch:
                    candidate = by_plan.get(plan.plan_id)
                    attempt = attempts.get(plan.plan_id, 0) + 1
                    if candidate is None:
                        self._reject(
                            plan,
                            attempt,
                            ["模型响应缺少该 plan_id"],
                            raw,
                        )
                        attempts[plan.plan_id] = attempt
                        continue
                    errors = validate_rag_document(
                        candidate.markdown,
                        self.config,
                    )
                    duplicate = deduplicator.check(candidate.markdown)
                    if duplicate is not None:
                        errors.append(
                            f"文档与 {duplicate.existing_id} "
                            f"{duplicate.kind} 重复，相似度 "
                            f"{duplicate.similarity:.1f}",
                        )
                    if errors:
                        self._reject(plan, attempt, errors, raw)
                        attempts[plan.plan_id] = attempt
                        continue

                    deduplicator.add(plan.plan_id, candidate.markdown)
                    filename = (
                        f"generated-{plan.plan_id}-"
                        f"{safe_filename(plan.topic)}.md"
                    )
                    relative_path = (
                        self.config.paths.rag_documents_dir / filename
                    ).as_posix()
                    record = AcceptedRecord(
                        plan=plan,
                        data={
                            "title": candidate.title,
                            "markdown": candidate.markdown,
                            "path": relative_path,
                        },
                    )
                    self.checkpoint.append_accepted(
                        "rag_documents",
                        record,
                    )
                    accepted[plan.plan_id] = record
                    attempts[plan.plan_id] = attempt

            self.progress(
                f"RAG documents checkpoint: {len(accepted)}/{len(all_plans)}",
            )
            pending = [
                plan
                for plan in selected
                if plan.plan_id not in accepted
                and attempts.get(plan.plan_id, 0)
                < self.config.generation.max_attempts_per_item
            ]

        exhausted = [
            plan.plan_id
            for plan in selected
            if plan.plan_id not in accepted
        ]
        if exhausted:
            raise GenerationIncompleteError(
                f"RAG 文档有 {len(exhausted)} 篇达到最大重试次数，示例: "
                + ", ".join(exhausted[:5]),
            )
        complete = all(plan.plan_id in accepted for plan in all_plans)
        outputs: tuple[str, ...] = ()
        if complete:
            outputs = self._export_rag_documents(all_plans, accepted)
            self.checkpoint.mark_complete("rag_documents", len(all_plans))
        return StageResult(
            stage="rag_documents",
            planned=len(selected),
            accepted=sum(plan.plan_id in accepted for plan in selected),
            completed=complete,
            output_files=outputs,
        )

    async def generate_rag_evaluation(
        self,
        *,
        limit: int | None = None,
    ) -> StageResult:
        documents = selected_document_manifests(self.config)
        all_plans = build_rag_evaluation_plan(self.config, documents)
        self.checkpoint.ensure_plan("rag_evaluation", all_plans)
        self.checkpoint.mark_started("rag_evaluation")
        selected = all_plans[:limit] if limit is not None else all_plans
        accepted = self.checkpoint.load_accepted("rag_evaluation")
        attempts = self.checkpoint.rejection_attempts("rag_evaluation")
        deduplicator = QuestionDeduplicator(self.config.deduplication)

        for record in sorted(
            accepted.values(),
            key=lambda item: item.plan.ordinal,
        ):
            item = RagEvalItem.model_validate(record.data)
            match = deduplicator.add(record.plan.plan_id, item.question)
            if match is not None:
                raise GenerationIncompleteError(
                    f"RAG evaluation checkpoint 中存在重复问题: "
                    f"{record.plan.plan_id} / {match.existing_id}",
                )

        pending = [
            plan
            for plan in selected
            if plan.plan_id not in accepted
            and attempts.get(plan.plan_id, 0)
            < self.config.generation.max_attempts_per_item
        ]
        while pending:
            concurrency = self._generation_concurrency
            batch_contexts: list[
                tuple[list[PlanItem], Path, str, str]
            ] = []
            seen_sources: set[str] = set()
            for first in pending:
                if first.source_document in seen_sources:
                    continue
                batch = [
                    plan
                    for plan in pending
                    if plan.source_document == first.source_document
                ][: self.config.rag_evaluation.batch_size]
                source_path = ensure_within(
                    self.output_root / first.source_document,
                    self.output_root,
                )
                source_content = source_path.read_text(encoding="utf-8")
                prompt_content = self._source_window(
                    source_content,
                    first.seed,
                )
                batch_contexts.append(
                    (batch, source_path, source_content, prompt_content),
                )
                seen_sources.add(first.source_document)
                if len(batch_contexts) >= concurrency:
                    break
            raw_responses = await asyncio.gather(
                *(
                    self._request_rag_eval_batch(
                        batch,
                        attempts,
                        prompt_content,
                    )
                    for batch, _, _, prompt_content in batch_contexts
                ),
            )
            for context, raw in zip(
                batch_contexts,
                raw_responses,
                strict=True,
            ):
                batch, source_path, source_content, _ = context
                candidates, parse_error = self._parse_candidates(
                    batch,
                    raw,
                    RagEvalCandidate,
                )
                if parse_error is not None:
                    self._reject_batch_parse_error(
                        batch,
                        attempts,
                        parse_error,
                        raw,
                    )
                    continue
                by_plan = {
                    candidate.plan_id: candidate
                    for candidate in candidates
                }
                for plan in batch:
                    candidate = by_plan.get(plan.plan_id)
                    attempt = attempts.get(plan.plan_id, 0) + 1
                    if candidate is None:
                        self._reject(
                            plan,
                            attempt,
                            ["模型响应缺少该 plan_id"],
                            raw,
                        )
                        attempts[plan.plan_id] = attempt
                        continue
                    item = RagEvalItem(
                        question=candidate.question,
                        answer=candidate.answer,
                        source_document=plan.source_document,
                        supporting_excerpt=candidate.supporting_excerpt,
                    )
                    errors = validate_rag_eval_item(
                        item,
                        source_path,
                        source_content,
                        self.config,
                    )
                    duplicate = deduplicator.check(item.question)
                    if duplicate is not None:
                        errors.append(
                            f"问题与 {duplicate.existing_id} "
                            f"{duplicate.kind} 重复，相似度 "
                            f"{duplicate.similarity:.1f}",
                        )
                    if errors:
                        self._reject(plan, attempt, errors, raw)
                        attempts[plan.plan_id] = attempt
                        continue

                    deduplicator.add(plan.plan_id, item.question)
                    record = AcceptedRecord(
                        plan=plan,
                        data=item.model_dump(mode="json"),
                    )
                    self.checkpoint.append_accepted(
                        "rag_evaluation",
                        record,
                    )
                    accepted[plan.plan_id] = record
                    attempts[plan.plan_id] = attempt

            self.progress(
                f"RAG evaluation checkpoint: {len(accepted)}/{len(all_plans)}",
            )
            pending = [
                plan
                for plan in selected
                if plan.plan_id not in accepted
                and attempts.get(plan.plan_id, 0)
                < self.config.generation.max_attempts_per_item
            ]

        exhausted = [
            plan.plan_id
            for plan in selected
            if plan.plan_id not in accepted
        ]
        if exhausted:
            raise GenerationIncompleteError(
                f"RAG 评测有 {len(exhausted)} 条达到最大重试次数，示例: "
                + ", ".join(exhausted[:5]),
            )
        complete = all(plan.plan_id in accepted for plan in all_plans)
        outputs: tuple[str, ...] = ()
        if complete:
            output_path = self.config.resolve_path(
                self.config.paths.evaluation_dir / "rag_test.jsonl",
            )
            atomic_write_jsonl(
                output_path,
                [
                    accepted[plan.plan_id].data
                    for plan in sorted(all_plans, key=lambda item: item.ordinal)
                ],
            )
            outputs = (str(output_path),)
            self.checkpoint.mark_complete("rag_evaluation", len(all_plans))
        return StageResult(
            stage="rag_evaluation",
            planned=len(selected),
            accepted=sum(plan.plan_id in accepted for plan in selected),
            completed=complete,
            output_files=outputs,
        )

    async def close(self) -> None:
        await self.provider.close()

    async def _request_sft_batch(
        self,
        batch: list[PlanItem],
        attempts: dict[str, int],
        *,
        stage: str,
        system_prompt_name: str,
    ) -> str:
        slots = [
            {
                "plan_id": plan.plan_id,
                "task_type": plan.category,
                "topic": plan.topic,
                "difficulty": plan.difficulty,
                "scenario": plan.scenario,
                "variation": plan.ordinal,
            }
            for plan in batch
        ]
        user_prompt = self.prompts.render(
            "sft-batch.md",
            slots_json=json.dumps(slots, ensure_ascii=False, indent=2),
            answer_min=self.config.lora.answer_min_chars,
            answer_max=self.config.lora.answer_max_chars,
            rejection_feedback=self._feedback(batch, attempts),
        )
        return await self._generate_with_usage(
            stage,
            GenerationRequest(
                system_prompt=self.prompts.render(system_prompt_name),
                user_prompt=user_prompt,
                seed=stable_seed(
                    self.config.seed,
                    "|".join(plan.plan_id for plan in batch)
                    + f":{max(attempts.get(plan.plan_id, 0) for plan in batch)}",
                ),
                json_mode=True,
            ),
        )

    async def _request_rag_document_batch(
        self,
        batch: list[PlanItem],
        attempts: dict[str, int],
    ) -> str:
        slots = [
            {
                "plan_id": plan.plan_id,
                "domain": plan.category,
                "topic": plan.topic,
                "variation": plan.ordinal,
            }
            for plan in batch
        ]
        return await self._generate_with_usage(
            "rag_documents",
            GenerationRequest(
                system_prompt=self.prompts.render("rag-document-system.md"),
                user_prompt=self.prompts.render(
                    "rag-document-batch.md",
                    slots_json=json.dumps(slots, ensure_ascii=False, indent=2),
                    min_chars=self.config.rag_documents.min_chars,
                    max_chars=self.config.rag_documents.max_chars,
                    rejection_feedback=self._feedback(batch, attempts),
                ),
                seed=stable_seed(
                    self.config.seed,
                    "|".join(plan.plan_id for plan in batch)
                    + f":{max(attempts.get(plan.plan_id, 0) for plan in batch)}",
                ),
                json_mode=True,
            ),
        )

    async def _request_rag_eval_batch(
        self,
        batch: list[PlanItem],
        attempts: dict[str, int],
        document_content: str,
    ) -> str:
        slots = [
            {
                "plan_id": plan.plan_id,
                "focus": plan.topic,
                "variation": plan.ordinal,
            }
            for plan in batch
        ]
        return await self._generate_with_usage(
            "rag_evaluation",
            GenerationRequest(
                system_prompt=self.prompts.render("rag-eval-system.md"),
                user_prompt=self.prompts.render(
                    "rag-eval-batch.md",
                    source_document=batch[0].source_document,
                    document_content=document_content,
                    slots_json=json.dumps(slots, ensure_ascii=False, indent=2),
                    answer_min=self.config.rag_evaluation.answer_min_chars,
                    answer_max=self.config.rag_evaluation.answer_max_chars,
                    excerpt_min=self.config.rag_evaluation.excerpt_min_chars,
                    excerpt_max=self.config.rag_evaluation.excerpt_max_chars,
                    rejection_feedback=self._feedback(batch, attempts),
                ),
                seed=stable_seed(
                    self.config.seed,
                    "|".join(plan.plan_id for plan in batch)
                    + f":{max(attempts.get(plan.plan_id, 0) for plan in batch)}",
                ),
                json_mode=True,
            ),
        )

    async def _generate_with_usage(
        self,
        stage: str,
        request: GenerationRequest,
    ) -> str:
        try:
            return await self.provider.generate(request)
        finally:
            snapshot = getattr(self.provider, "usage_stats", {})
            if isinstance(snapshot, dict):
                fields = set(snapshot) | set(self._last_usage_snapshot)
                delta = {
                    field: int(snapshot.get(field, 0))
                    - int(self._last_usage_snapshot.get(field, 0))
                    for field in fields
                }
                self.checkpoint.append_usage(stage, delta)
                self._last_usage_snapshot = {
                    field: int(value)
                    for field, value in snapshot.items()
                }

    def _parse_candidates(
        self,
        batch: list[PlanItem],
        raw: str,
        model_class: type[Any],
    ) -> tuple[list[Any], str | None]:
        allowed = {plan.plan_id for plan in batch}
        try:
            payload = parse_json_output(
                raw,
                max_chars=self.config.generation.response_max_chars,
            )
            raw_items = extract_items(payload)
        except ModelOutputParseError as exc:
            return [], str(exc)

        candidates: list[Any] = []
        seen: set[str] = set()
        for raw_item in raw_items:
            try:
                candidate = model_class.model_validate(raw_item)
            except ValidationError:
                continue
            if candidate.plan_id not in allowed or candidate.plan_id in seen:
                continue
            candidates.append(candidate)
            seen.add(candidate.plan_id)
        return candidates, None

    def _reject_batch_parse_error(
        self,
        batch: list[PlanItem],
        attempts: dict[str, int],
        message: str,
        raw: str,
    ) -> None:
        for plan in batch:
            attempt = attempts.get(plan.plan_id, 0) + 1
            self._reject(plan, attempt, [message], raw)
            attempts[plan.plan_id] = attempt

    def _reject(
        self,
        plan: PlanItem,
        attempt: int,
        reasons: list[str],
        raw: str,
    ) -> None:
        self.checkpoint.append_rejected(
            plan.stage,
            RejectedRecord(
                plan_id=plan.plan_id,
                stage=plan.stage,
                attempt=attempt,
                reasons=reasons,
                raw_preview=raw[:1000],
                quality_rule_version=4,
            ),
        )

    @staticmethod
    def _feedback(
        batch: list[PlanItem],
        attempts: dict[str, int],
    ) -> str:
        retried = [
            plan.plan_id
            for plan in batch
            if attempts.get(plan.plan_id, 0) > 0
        ]
        if not retried:
            return ""
        return (
            "以下槽位是重新生成项，请特别检查长度、字段和工程细节："
            + "、".join(retried)
        )

    def _source_window(self, content: str, seed: int) -> str:
        maximum = self.config.rag_evaluation.max_source_chars_per_batch
        if len(content) <= maximum:
            return content
        start = seed % (len(content) - maximum + 1)
        # 尽量从段落边界开始，避免截断证据句。
        paragraph_start = content.find("\n\n", start)
        if paragraph_start >= 0 and paragraph_start < start + 500:
            start = paragraph_start + 2
        return content[start : start + maximum]

    def _export_sft(
        self,
        plans: list[PlanItem],
        accepted: dict[str, AcceptedRecord],
    ) -> tuple[str, ...]:
        lora_dir = self.config.resolve_path(self.config.paths.lora_dir)
        outputs: list[str] = []
        manifest: list[dict[str, Any]] = []
        for split in ("train", "val", "test"):
            split_plans = sorted(
                (plan for plan in plans if plan.split == split),
                key=lambda item: item.ordinal,
            )
            records = [
                accepted[plan.plan_id].data
                for plan in split_plans
            ]
            path = lora_dir / f"{split}.jsonl"
            atomic_write_jsonl(path, records)
            outputs.append(str(path))
            for plan, data in zip(split_plans, records, strict=True):
                manifest.append(
                    {
                        "plan_id": plan.plan_id,
                        "split": split,
                        "task_type": plan.category,
                        "record_sha256": sha256_text(
                            json.dumps(
                                data,
                                ensure_ascii=False,
                                sort_keys=True,
                            ),
                        ),
                    },
                )
        manifest_path = lora_dir / "manifest.jsonl"
        atomic_write_jsonl(manifest_path, manifest)
        outputs.append(str(manifest_path))
        return tuple(outputs)

    def _export_lora_evaluation(
        self,
        plans: list[PlanItem],
        accepted: dict[str, AcceptedRecord],
    ) -> tuple[str, ...]:
        evaluation_dir = self.config.resolve_path(
            self.config.paths.evaluation_dir,
        )
        ordered = sorted(plans, key=lambda item: item.ordinal)
        records = [accepted[plan.plan_id].data for plan in ordered]
        output_path = evaluation_dir / "lora_test.jsonl"
        atomic_write_jsonl(output_path, records)
        manifest_path = evaluation_dir / "lora_manifest.jsonl"
        atomic_write_jsonl(
            manifest_path,
            [
                {
                    "plan_id": plan.plan_id,
                    "task_type": plan.category,
                    "record_sha256": sha256_text(
                        json.dumps(
                            data,
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                    ),
                }
                for plan, data in zip(ordered, records, strict=True)
            ],
        )
        return str(output_path), str(manifest_path)

    def _export_rag_documents(
        self,
        plans: list[PlanItem],
        accepted: dict[str, AcceptedRecord],
    ) -> tuple[str, ...]:
        documents_dir = self.config.resolve_path(
            self.config.paths.rag_documents_dir,
        )
        manifest_items: list[DocumentManifestItem] = []
        outputs: list[str] = []
        for plan in sorted(plans, key=lambda item: item.ordinal):
            data = accepted[plan.plan_id].data
            path = ensure_within(
                self.output_root / str(data["path"]),
                self.output_root,
            )
            markdown = str(data["markdown"]).strip() + "\n"
            atomic_write_text(path, markdown)
            outputs.append(str(path))
            manifest_items.append(
                DocumentManifestItem(
                    plan_id=plan.plan_id,
                    path=path.relative_to(self.output_root).as_posix(),
                    source_type="generated",
                    sha256=sha256_text(markdown),
                    domain=plan.category,
                    topic=plan.topic,
                ),
            )
        manifest_path = documents_dir.parent / "generated_manifest.jsonl"
        atomic_write_jsonl(
            manifest_path,
            [item.model_dump(mode="json") for item in manifest_items],
        )
        outputs.append(str(manifest_path))
        return tuple(outputs)
