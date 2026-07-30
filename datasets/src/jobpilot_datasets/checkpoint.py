"""生成计划、接受样本与拒绝原因的断点恢复存储。"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from jobpilot_datasets.io_utils import (
    append_jsonl,
    atomic_write_json,
    atomic_write_jsonl,
    read_jsonl,
)
from jobpilot_datasets.models import AcceptedRecord, PlanItem, RejectedRecord
from jobpilot_datasets.text_utils import sha256_text


class CheckpointConflictError(RuntimeError):
    """工作目录与当前配置或计划不兼容。"""


class CheckpointStore:
    def __init__(
        self,
        work_dir: Path,
        *,
        config_fingerprint: str,
        seed: int,
        resume: bool,
    ) -> None:
        self.work_dir = work_dir
        self.plan_dir = work_dir / "plans"
        self.accepted_dir = work_dir / "accepted"
        self.rejected_dir = work_dir / "rejected"
        self.usage_path = work_dir / "usage.jsonl"
        self.manifest_path = work_dir / "manifest.json"
        self._initialize(config_fingerprint, seed, resume)

    def _initialize(self, fingerprint: str, seed: int, resume: bool) -> None:
        if self.manifest_path.exists():
            current = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            if current.get("config_fingerprint") != fingerprint:
                raise CheckpointConflictError(
                    "checkpoint 配置指纹不一致，请更换 work_dir 或清理旧工作目录",
                )
            has_records = any(self.accepted_dir.glob("*.jsonl"))
            if has_records and not resume:
                raise CheckpointConflictError(
                    "检测到未清理的 checkpoint，请使用 --resume 继续",
                )
            return

        self.work_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_json(
            self.manifest_path,
            {
                "config_fingerprint": fingerprint,
                "seed": seed,
                "created_at": datetime.now(UTC).isoformat(),
                "stages": {},
            },
        )

    def set_run_metadata(self, metadata: dict[str, object]) -> None:
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        if manifest.get("run_metadata") == metadata:
            return
        manifest["run_metadata"] = metadata
        atomic_write_json(self.manifest_path, manifest)

    def mark_started(self, stage: str) -> None:
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        stage_data = manifest.setdefault("stages", {}).setdefault(stage, {})
        stage_data.setdefault("started_at", datetime.now(UTC).isoformat())
        stage_data["status"] = "in_progress"
        atomic_write_json(self.manifest_path, manifest)

    def ensure_plan(self, stage: str, plans: list[PlanItem]) -> None:
        path = self.plan_dir / f"{stage}.jsonl"
        records = [plan.model_dump(mode="json") for plan in plans]
        serialized = "\n".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True)
            for item in records
        )
        plan_hash = sha256_text(serialized)
        if path.exists():
            existing = "\n".join(
                json.dumps(item, ensure_ascii=False, sort_keys=True)
                for _, item in read_jsonl(path)
            )
            if sha256_text(existing) != plan_hash:
                raise CheckpointConflictError(
                    f"{stage} 生成计划发生变化，请使用新的 work_dir",
                )
            return
        atomic_write_jsonl(path, records)

    def load_accepted(self, stage: str) -> dict[str, AcceptedRecord]:
        path = self.accepted_dir / f"{stage}.jsonl"
        if not path.exists():
            return {}
        records: dict[str, AcceptedRecord] = {}
        for _, payload in read_jsonl(path):
            record = AcceptedRecord.model_validate(payload)
            records[record.plan.plan_id] = record
        return records

    def append_accepted(self, stage: str, record: AcceptedRecord) -> None:
        append_jsonl(
            self.accepted_dir / f"{stage}.jsonl",
            record.model_dump(mode="json"),
        )

    def rejection_attempts(
        self,
        stage: str,
        *,
        quality_rule_version: int = 4,
    ) -> dict[str, int]:
        path = self.rejected_dir / f"{stage}.jsonl"
        attempts: dict[str, int] = {}
        if not path.exists():
            return attempts
        for _, payload in read_jsonl(path):
            record = RejectedRecord.model_validate(payload)
            if record.quality_rule_version != quality_rule_version:
                continue
            attempts[record.plan_id] = max(
                attempts.get(record.plan_id, 0),
                record.attempt,
            )
        return attempts

    def append_rejected(self, stage: str, record: RejectedRecord) -> None:
        append_jsonl(
            self.rejected_dir / f"{stage}.jsonl",
            record.model_dump(mode="json"),
        )

    def mark_complete(self, stage: str, count: int) -> None:
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        stage_data = manifest.setdefault("stages", {}).setdefault(stage, {})
        stage_data.update(
            {
                "status": "complete",
                "count": count,
                "completed_at": datetime.now(UTC).isoformat(),
            },
        )
        atomic_write_json(self.manifest_path, manifest)

    def append_usage(self, stage: str, delta: dict[str, int]) -> None:
        if not any(delta.values()):
            return
        append_jsonl(
            self.usage_path,
            {
                "stage": stage,
                "captured_at": datetime.now(UTC).isoformat(),
                **delta,
            },
        )

    def usage_summary(self) -> dict[str, int]:
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
        if not self.usage_path.exists():
            return summary
        for _, payload in read_jsonl(self.usage_path):
            for field in fields:
                value = payload.get(field, 0)
                if isinstance(value, int):
                    summary[field] += value
        return summary
