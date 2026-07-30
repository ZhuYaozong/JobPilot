"""最终数据集质量检查与报告。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from pydantic import ValidationError

from jobpilot_datasets.config import AppConfig
from jobpilot_datasets.deduplication import QuestionDeduplicator
from jobpilot_datasets.io_utils import (
    JsonlReadError,
    atomic_write_json,
    atomic_write_text,
    read_jsonl,
)
from jobpilot_datasets.models import (
    DocumentManifestItem,
    QualityIssue,
    QualityReport,
    RagEvalItem,
    SFTItem,
)
from jobpilot_datasets.sources import load_manifest
from jobpilot_datasets.text_utils import (
    ensure_within,
    sha256_text,
    visible_char_count,
)
from jobpilot_datasets.validation import (
    validate_rag_document,
    validate_rag_eval_item,
    validate_sft_item,
)


class QualityInspector:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.output_root = config.resolve_path(Path("."))
        self.issues: list[QualityIssue] = []
        self.counts: dict[str, int] = {}
        self.distributions: dict[str, dict[str, int]] = {}
        self.duplicate_stats = {"exact": 0, "near": 0}
        self.statistics: dict[str, dict[str, float]] = {}
        self._sft_deduplicator = QuestionDeduplicator(
            self.config.deduplication,
        )
        self._sft_schema = self._load_schema("sft-item.schema.json")
        self._rag_eval_schema = self._load_schema("rag-eval-item.schema.json")

    def run(self, *, allow_missing: bool = False) -> QualityReport:
        self._inspect_sft(allow_missing=allow_missing)
        self._inspect_lora_evaluation(allow_missing=allow_missing)
        self._inspect_rag_documents(allow_missing=allow_missing)
        self._inspect_rag_evaluation(allow_missing=allow_missing)
        rejection_stats = self._rejection_summary()
        generation = self._generation_summary()
        api_usage = self._api_usage_summary()

        has_errors = any(issue.severity == "error" for issue in self.issues)
        has_warnings = any(issue.severity == "warning" for issue in self.issues)
        passed = not has_errors and not (
            self.config.quality.fail_on_warning and has_warnings
        )
        report = QualityReport(
            created_at=datetime.now(UTC).isoformat(),
            passed=passed,
            counts=self.counts,
            distributions=self.distributions,
            duplicate_stats=self.duplicate_stats,
            statistics=self.statistics,
            rejection_stats=rejection_stats,
            generation=generation,
            api_usage=api_usage,
            issues=self.issues,
        )
        self._write_report(report)
        return report

    def _inspect_sft(self, *, allow_missing: bool) -> None:
        lora_dir = self.config.resolve_path(self.config.paths.lora_dir)
        actual_hashes: set[str] = set()
        for split, expected in self.config.lora.splits.items():
            path = lora_dir / f"{split}.jsonl"
            key = f"lora_{split}"
            if not path.exists():
                self.counts[key] = 0
                self._missing(path, allow_missing)
                continue
            count = 0
            instruction_total = 0
            input_total = 0
            output_total = 0
            for line_number, payload in self._safe_read(path):
                count += 1
                if not self._schema_valid(
                    self._sft_schema,
                    payload,
                    path,
                    line_number,
                ):
                    continue
                try:
                    item = SFTItem.model_validate(payload)
                except ValidationError as exc:
                    self._error(
                        "sft_pydantic",
                        str(exc),
                        path,
                        line_number,
                    )
                    continue
                for reason in validate_sft_item(item, self.config):
                    self._error("sft_quality", reason, path, line_number)
                instruction_total += visible_char_count(item.instruction)
                input_total += visible_char_count(item.input)
                output_total += visible_char_count(item.output)
                duplicate = self._sft_deduplicator.add(
                    f"{split}:{line_number}",
                    f"{item.instruction}\n{item.input}",
                )
                if duplicate is not None:
                    kind = duplicate.kind if duplicate.kind in {"exact", "near"} else "exact"
                    self.duplicate_stats[kind] += 1
                    self._error(
                        "sft_duplicate",
                        f"与 {duplicate.existing_id} 重复，"
                        f"相似度 {duplicate.similarity:.1f}",
                        path,
                        line_number,
                    )
                actual_hashes.add(
                    sha256_text(
                        json.dumps(
                            payload,
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                    ),
                )
            self.counts[key] = count
            self.statistics[key] = {
                "count": float(count),
                "instruction_avg_chars": (
                    instruction_total / count if count else 0.0
                ),
                "input_avg_chars": input_total / count if count else 0.0,
                "output_avg_chars": output_total / count if count else 0.0,
            }
            if count != expected:
                self._error(
                    "sft_count",
                    f"{split} 实际 {count} 条，期望 {expected} 条",
                    path,
                )

        manifest_path = lora_dir / "manifest.jsonl"
        if not manifest_path.exists():
            self._missing(manifest_path, allow_missing)
            return
        distribution: dict[str, int] = {}
        manifest_count = 0
        for line_number, payload in self._safe_read(manifest_path):
            manifest_count += 1
            split = str(payload.get("split", ""))
            task_type = str(payload.get("task_type", ""))
            record_hash = str(payload.get("record_sha256", ""))
            key = f"{split}/{task_type}"
            distribution[key] = distribution.get(key, 0) + 1
            if task_type not in self.config.lora.task_types:
                self._error(
                    "sft_manifest_task_type",
                    f"未知任务类型: {task_type}",
                    manifest_path,
                    line_number,
                )
            if record_hash not in actual_hashes:
                self._error(
                    "sft_manifest_hash",
                    "manifest 记录在最终数据中不存在",
                    manifest_path,
                    line_number,
                )
        self.counts["lora_manifest"] = manifest_count
        self.distributions["lora_task_types"] = distribution

        expected_manifest = sum(self.config.lora.splits.values())
        if manifest_count != expected_manifest:
            self._error(
                "sft_manifest_count",
                f"manifest 实际 {manifest_count} 条，期望 {expected_manifest} 条",
                manifest_path,
            )
        for split, split_total in self.config.lora.splits.items():
            expected_per_type = split_total // len(self.config.lora.task_types)
            for task_type in self.config.lora.task_types:
                actual = distribution.get(f"{split}/{task_type}", 0)
                if actual != expected_per_type:
                    self._error(
                        "sft_task_distribution",
                        f"{split}/{task_type} 实际 {actual} 条，"
                        f"期望 {expected_per_type} 条",
                        manifest_path,
                    )

    def _inspect_lora_evaluation(self, *, allow_missing: bool) -> None:
        evaluation_dir = self.config.resolve_path(
            self.config.paths.evaluation_dir,
        )
        path = evaluation_dir / "lora_test.jsonl"
        if not path.exists():
            self.counts["lora_evaluation"] = 0
            self._missing(path, allow_missing)
            return

        count = 0
        instruction_total = 0
        input_total = 0
        output_total = 0
        actual_hashes: set[str] = set()
        for line_number, payload in self._safe_read(path):
            count += 1
            if not self._schema_valid(
                self._sft_schema,
                payload,
                path,
                line_number,
            ):
                continue
            try:
                item = SFTItem.model_validate(payload)
            except ValidationError as exc:
                self._error(
                    "lora_eval_pydantic",
                    str(exc),
                    path,
                    line_number,
                )
                continue
            for reason in validate_sft_item(item, self.config):
                self._error(
                    "lora_eval_quality",
                    reason,
                    path,
                    line_number,
                )
            instruction_total += visible_char_count(item.instruction)
            input_total += visible_char_count(item.input)
            output_total += visible_char_count(item.output)
            duplicate = self._sft_deduplicator.add(
                f"lora_evaluation:{line_number}",
                f"{item.instruction}\n{item.input}",
            )
            if duplicate is not None:
                kind = (
                    duplicate.kind
                    if duplicate.kind in {"exact", "near"}
                    else "exact"
                )
                self.duplicate_stats[kind] += 1
                self._error(
                    "lora_eval_leakage",
                    f"与 SFT/LoRA evaluation 中的 {duplicate.existing_id} "
                    f"重复，相似度 {duplicate.similarity:.1f}",
                    path,
                    line_number,
                )
            actual_hashes.add(
                sha256_text(
                    json.dumps(
                        payload,
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                ),
            )

        self.counts["lora_evaluation"] = count
        self.statistics["lora_evaluation"] = {
            "count": float(count),
            "instruction_avg_chars": (
                instruction_total / count if count else 0.0
            ),
            "input_avg_chars": input_total / count if count else 0.0,
            "output_avg_chars": output_total / count if count else 0.0,
        }
        if count != self.config.lora_evaluation.total:
            self._error(
                "lora_eval_count",
                f"LoRA evaluation 实际 {count} 条，"
                f"期望 {self.config.lora_evaluation.total} 条",
                path,
            )

        manifest_path = evaluation_dir / "lora_manifest.jsonl"
        if not manifest_path.exists():
            self._missing(manifest_path, allow_missing)
            return
        distribution: dict[str, int] = {}
        manifest_count = 0
        for line_number, payload in self._safe_read(manifest_path):
            manifest_count += 1
            task_type = str(payload.get("task_type", ""))
            record_hash = str(payload.get("record_sha256", ""))
            distribution[task_type] = distribution.get(task_type, 0) + 1
            if task_type not in self.config.lora.task_types:
                self._error(
                    "lora_eval_manifest_task_type",
                    f"未知任务类型: {task_type}",
                    manifest_path,
                    line_number,
                )
            if record_hash not in actual_hashes:
                self._error(
                    "lora_eval_manifest_hash",
                    "manifest 记录在最终评测数据中不存在",
                    manifest_path,
                    line_number,
                )
        self.counts["lora_evaluation_manifest"] = manifest_count
        self.distributions["lora_evaluation_task_types"] = distribution
        if manifest_count != self.config.lora_evaluation.total:
            self._error(
                "lora_eval_manifest_count",
                f"manifest 实际 {manifest_count} 条，"
                f"期望 {self.config.lora_evaluation.total} 条",
                manifest_path,
            )
        base_count, remainder = divmod(
            self.config.lora_evaluation.total,
            len(self.config.lora.task_types),
        )
        for index, task_type in enumerate(self.config.lora.task_types):
            expected = base_count + (1 if index < remainder else 0)
            actual = distribution.get(task_type, 0)
            if actual != expected:
                self._error(
                    "lora_eval_task_distribution",
                    f"{task_type} 实际 {actual} 条，期望 {expected} 条",
                    manifest_path,
                )

    def _inspect_rag_documents(self, *, allow_missing: bool) -> None:
        documents_dir = self.config.resolve_path(
            self.config.paths.rag_documents_dir,
        )
        manifest_path = documents_dir.parent / "generated_manifest.jsonl"
        if not manifest_path.exists():
            self.counts["rag_generated_documents"] = 0
            self._missing(manifest_path, allow_missing)
            return
        manifest = load_manifest(manifest_path)
        self.counts["rag_generated_documents"] = len(manifest)
        if len(manifest) != self.config.rag_documents.total:
            self._error(
                "rag_document_count",
                f"生成文档实际 {len(manifest)} 篇，"
                f"期望 {self.config.rag_documents.total} 篇",
                manifest_path,
            )
        domain_distribution: dict[str, int] = {}
        document_total_chars = 0
        document_deduplicator = QuestionDeduplicator(
            self.config.deduplication,
        )
        for item in manifest:
            domain_distribution[item.domain] = (
                domain_distribution.get(item.domain, 0) + 1
            )
            path = self._resolve_source(item, manifest_path)
            if path is None:
                continue
            content = path.read_text(encoding="utf-8")
            document_total_chars += visible_char_count(
                content,
                strip_markdown=True,
            )
            duplicate = document_deduplicator.add(item.plan_id, content)
            if duplicate is not None:
                kind = (
                    duplicate.kind
                    if duplicate.kind in {"exact", "near"}
                    else "exact"
                )
                self.duplicate_stats[kind] += 1
                self._error(
                    "rag_document_duplicate",
                    f"与 {duplicate.existing_id} 重复，"
                    f"相似度 {duplicate.similarity:.1f}",
                    path,
                )
            if sha256_text(content) != item.sha256:
                self._error(
                    "rag_document_hash",
                    "文档内容与 manifest 哈希不一致",
                    path,
                )
            for reason in validate_rag_document(content, self.config):
                self._error("rag_document_quality", reason, path)
        self.distributions["rag_domains"] = domain_distribution
        self.statistics["rag_generated_documents"] = {
            "count": float(len(manifest)),
            "document_avg_chars": (
                document_total_chars / len(manifest) if manifest else 0.0
            ),
        }
        base_count, remainder = divmod(
            self.config.rag_documents.total,
            len(self.config.rag_documents.domains),
        )
        for index, domain in enumerate(self.config.rag_documents.domains):
            expected = base_count + (1 if index < remainder else 0)
            actual = domain_distribution.get(domain, 0)
            if actual != expected:
                self._error(
                    "rag_domain_distribution",
                    f"{domain} 实际 {actual} 篇，期望 {expected} 篇",
                    manifest_path,
                )

        external_manifest = documents_dir.parent / "external_manifest.jsonl"
        external = load_manifest(external_manifest)
        self.counts["rag_external_documents"] = len(external)
        for item in external:
            self._resolve_source(item, external_manifest)

    def _inspect_rag_evaluation(self, *, allow_missing: bool) -> None:
        path = self.config.resolve_path(
            self.config.paths.evaluation_dir / "rag_test.jsonl",
        )
        if not path.exists():
            self.counts["rag_evaluation"] = 0
            self._missing(path, allow_missing)
            return
        count = 0
        question_total = 0
        answer_total = 0
        excerpt_total = 0
        source_distribution: dict[str, int] = {}
        deduplicator = QuestionDeduplicator(self.config.deduplication)
        for line_number, payload in self._safe_read(path):
            count += 1
            if not self._schema_valid(
                self._rag_eval_schema,
                payload,
                path,
                line_number,
            ):
                continue
            try:
                item = RagEvalItem.model_validate(payload)
            except ValidationError as exc:
                self._error(
                    "rag_eval_pydantic",
                    str(exc),
                    path,
                    line_number,
                )
                continue
            question_total += visible_char_count(item.question)
            answer_total += visible_char_count(item.answer)
            excerpt_total += visible_char_count(item.supporting_excerpt)
            duplicate = deduplicator.add(
                f"rag_eval:{line_number}",
                item.question,
            )
            if duplicate is not None:
                kind = duplicate.kind if duplicate.kind in {"exact", "near"} else "exact"
                self.duplicate_stats[kind] += 1
                self._error(
                    "rag_eval_duplicate",
                    f"与 {duplicate.existing_id} 重复，"
                    f"相似度 {duplicate.similarity:.1f}",
                    path,
                    line_number,
                )

            try:
                source_path = ensure_within(
                    self.output_root / item.source_document,
                    self.output_root,
                )
            except ValueError as exc:
                self._error(
                    "rag_eval_source_path",
                    str(exc),
                    path,
                    line_number,
                )
                continue
            if not source_path.exists():
                self._error(
                    "rag_eval_source_missing",
                    f"源文档不存在: {item.source_document}",
                    path,
                    line_number,
                )
                continue
            source_content = source_path.read_text(encoding="utf-8")
            for reason in validate_rag_eval_item(
                item,
                source_path,
                source_content,
                self.config,
            ):
                self._error(
                    "rag_eval_quality",
                    reason,
                    path,
                    line_number,
                )
            source_distribution[item.source_document] = (
                source_distribution.get(item.source_document, 0) + 1
            )
        self.counts["rag_evaluation"] = count
        self.statistics["rag_evaluation"] = {
            "count": float(count),
            "question_avg_chars": question_total / count if count else 0.0,
            "answer_avg_chars": answer_total / count if count else 0.0,
            "excerpt_avg_chars": excerpt_total / count if count else 0.0,
        }
        self.distributions["rag_evaluation_sources"] = source_distribution
        if count != self.config.rag_evaluation.total:
            self._error(
                "rag_eval_count",
                f"RAG 评测实际 {count} 条，"
                f"期望 {self.config.rag_evaluation.total} 条",
                path,
            )

    def _rejection_summary(self) -> dict[str, Any]:
        rejected_dir = (
            self.config.resolve_path(self.config.paths.work_dir) / "rejected"
        )
        by_stage: dict[str, int] = {}
        by_reason: dict[str, int] = {}
        unique_plan_ids: set[str] = set()
        if rejected_dir.exists():
            for path in sorted(rejected_dir.glob("*.jsonl")):
                for _, payload in self._safe_read(path):
                    stage = str(payload.get("stage", path.stem))
                    by_stage[stage] = by_stage.get(stage, 0) + 1
                    unique_plan_ids.add(str(payload.get("plan_id", "")))
                    reasons = payload.get("reasons", [])
                    if not isinstance(reasons, list):
                        reasons = [str(reasons)]
                    for reason in reasons:
                        key = self._rejection_reason_key(str(reason))
                        by_reason[key] = by_reason.get(key, 0) + 1
        return {
            "total_rejection_events": sum(by_stage.values()),
            "unique_rejected_plan_ids": len(unique_plan_ids - {""}),
            "by_stage": by_stage,
            "by_reason": by_reason,
        }

    @staticmethod
    def _rejection_reason_key(reason: str) -> str:
        mappings = (
            ("instruction 有效长度", "instruction_length"),
            ("output 有效长度", "output_length"),
            ("answer 有效长度", "answer_length"),
            ("supporting_excerpt 有效长度", "excerpt_length"),
            ("工程实践信号", "engineering_signals"),
            ("不是源文档", "excerpt_not_in_source"),
            ("缺少“##", "missing_markdown_section"),
            ("缺少一级标题", "missing_markdown_title"),
            ("文档有效长度", "document_length"),
            ("重复", "duplicate"),
            ("plan_id", "missing_or_invalid_plan_id"),
            ("不是有效 JSON", "json_parse"),
            ("必须是数组", "json_shape"),
            ("占位或空泛", "boilerplate"),
        )
        for marker, key in mappings:
            if marker in reason:
                return key
        return reason[:120] or "unknown"

    def _generation_summary(self) -> dict[str, Any]:
        manifest_path = (
            self.config.resolve_path(self.config.paths.work_dir)
            / "manifest.json"
        )
        if not manifest_path.exists():
            return {}
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        stages = payload.get("stages", {})
        timestamps: list[datetime] = []
        for stage_data in stages.values():
            if not isinstance(stage_data, dict):
                continue
            for field in ("started_at", "completed_at"):
                value = stage_data.get(field)
                if isinstance(value, str):
                    try:
                        timestamps.append(datetime.fromisoformat(value))
                    except ValueError:
                        pass
        duration = (
            (max(timestamps) - min(timestamps)).total_seconds()
            if len(timestamps) >= 2
            else 0.0
        )
        return {
            "config_fingerprint": payload.get("config_fingerprint", ""),
            "seed": payload.get("seed"),
            "run_metadata": payload.get("run_metadata", {}),
            "stages": stages,
            "elapsed_seconds": duration,
        }

    def _api_usage_summary(self) -> dict[str, int]:
        usage_path = (
            self.config.resolve_path(self.config.paths.work_dir)
            / "usage.jsonl"
        )
        fields = (
            "request_attempts",
            "successful_responses",
            "failed_attempts",
            "usage_reported_responses",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "prompt_cache_hit_tokens",
            "prompt_cache_miss_tokens",
        )
        summary = {field: 0 for field in fields}
        if not usage_path.exists():
            return summary
        for _, payload in self._safe_read(usage_path):
            for field in fields:
                value = payload.get(field, 0)
                if isinstance(value, int):
                    summary[field] += value
        return summary

    def _load_schema(self, name: str) -> Draft202012Validator:
        path = self.config.resolve_path(self.config.paths.schemas_dir) / name
        payload = json.loads(path.read_text(encoding="utf-8"))
        return Draft202012Validator(payload)

    def _schema_valid(
        self,
        validator: Draft202012Validator,
        payload: dict[str, Any],
        path: Path,
        line: int,
    ) -> bool:
        errors = sorted(validator.iter_errors(payload), key=lambda item: list(item.path))
        for error in errors:
            self._error("json_schema", error.message, path, line)
        return not errors

    def _safe_read(self, path: Path) -> list[tuple[int, dict[str, Any]]]:
        try:
            return list(read_jsonl(path))
        except JsonlReadError as exc:
            self._error("jsonl_parse", str(exc), path, exc.line)
            return []

    def _resolve_source(
        self,
        item: DocumentManifestItem,
        manifest_path: Path,
    ) -> Path | None:
        try:
            path = ensure_within(
                self.output_root / item.path,
                self.output_root,
            )
        except ValueError as exc:
            self._error("manifest_path", str(exc), manifest_path)
            return None
        if not path.exists():
            self._error(
                "manifest_source_missing",
                f"清单中的文档不存在: {item.path}",
                manifest_path,
            )
            return None
        return path

    def _missing(self, path: Path, allow_missing: bool) -> None:
        severity = "warning" if allow_missing else "error"
        self.issues.append(
            QualityIssue(
                severity=severity,
                code="file_missing",
                message="文件不存在",
                file=str(path),
            ),
        )

    def _error(
        self,
        code: str,
        message: str,
        path: Path,
        line: int | None = None,
    ) -> None:
        self.issues.append(
            QualityIssue(
                severity="error",
                code=code,
                message=message,
                file=str(path),
                line=line,
            ),
        )

    def _write_report(self, report: QualityReport) -> None:
        reports_dir = self.config.resolve_path(self.config.paths.reports_dir)
        atomic_write_json(
            reports_dir / "quality_report.json",
            report.model_dump(mode="json"),
        )
        lines = [
            "# JobPilot 数据质量报告",
            "",
            f"- 生成时间：{report.created_at}",
            f"- 结论：{'通过' if report.passed else '未通过'}",
            f"- 错误数：{sum(i.severity == 'error' for i in report.issues)}",
            f"- 警告数：{sum(i.severity == 'warning' for i in report.issues)}",
            f"- 生成模型：{report.generation.get('run_metadata', {}).get('model', '-')}",
            f"- API endpoint：{report.generation.get('run_metadata', {}).get('base_url', '-')}",
            f"- 生成耗时：{report.generation.get('elapsed_seconds', 0):.1f} 秒",
            "",
            "## 数据量",
            "",
            "| 数据集 | 数量 |",
            "| --- | ---: |",
        ]
        lines.extend(
            f"| {name} | {count} |"
            for name, count in sorted(report.counts.items())
        )
        lines.extend(
            [
                "",
                "## API 与 Token",
                "",
                f"- HTTP 请求尝试：{report.api_usage.get('request_attempts', 0)}",
                f"- 成功响应：{report.api_usage.get('successful_responses', 0)}",
                f"- 失败尝试：{report.api_usage.get('failed_attempts', 0)}",
                f"- Prompt tokens：{report.api_usage.get('prompt_tokens', 0)}",
                f"- Completion tokens：{report.api_usage.get('completion_tokens', 0)}",
                f"- Total tokens：{report.api_usage.get('total_tokens', 0)}",
                "",
                "## 平均长度",
                "",
                "| 数据集 | 指标 | 平均值 |",
                "| --- | --- | ---: |",
            ],
        )
        for dataset, metrics in sorted(report.statistics.items()):
            for metric, value in sorted(metrics.items()):
                if metric == "count":
                    continue
                lines.append(f"| {dataset} | {metric} | {value:.2f} |")
        lines.extend(
            [
                "",
                "## 拒绝与补生成",
                "",
                f"- 拒绝事件：{report.rejection_stats.get('total_rejection_events', 0)}",
                f"- 曾被拒绝的计划项：{report.rejection_stats.get('unique_rejected_plan_ids', 0)}",
                "",
                "| 原因 | 次数 |",
                "| --- | ---: |",
            ],
        )
        for reason, count in sorted(
            report.rejection_stats.get("by_reason", {}).items(),
            key=lambda item: (-item[1], item[0]),
        ):
            lines.append(f"| {reason} | {count} |")
        lines.extend(
            [
                "",
                "## 分类分布",
                "",
            ],
        )
        for distribution_name, values in sorted(report.distributions.items()):
            lines.append(f"### {distribution_name}")
            lines.append("")
            lines.append("| 分类 | 数量 |")
            lines.append("| --- | ---: |")
            lines.extend(
                f"| {name} | {count} |"
                for name, count in sorted(values.items())
            )
            lines.append("")
        lines.extend(
            [
                "",
                "## 重复统计",
                "",
                f"- 精确重复：{report.duplicate_stats.get('exact', 0)}",
                f"- 近似重复：{report.duplicate_stats.get('near', 0)}",
                "",
                "## 问题明细",
                "",
            ],
        )
        if not report.issues:
            lines.append("未发现问题。")
        else:
            lines.extend(
                (
                    f"- [{issue.severity}] `{issue.code}` "
                    f"{issue.file}"
                    f"{':' + str(issue.line) if issue.line else ''}："
                    f"{issue.message}"
                )
                for issue in report.issues
            )
        atomic_write_text(
            reports_dir / "quality_report.md",
            "\n".join(lines) + "\n",
        )
