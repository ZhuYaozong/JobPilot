"""数据记录、计划与报告模型。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SFTItem(StrictModel):
    instruction: str
    input: str
    output: str

    @field_validator("instruction", "output")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("字段不能为空")
        return value

    @field_validator("input")
    @classmethod
    def strip_optional_input(cls, value: str) -> str:
        return value.strip()


class SFTCandidate(SFTItem):
    plan_id: str


class RagEvalItem(StrictModel):
    question: str
    answer: str
    source_document: str
    supporting_excerpt: str

    @field_validator("*")
    @classmethod
    def strip_non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("字段不能为空")
        return value


class RagEvalCandidate(StrictModel):
    plan_id: str
    question: str
    answer: str
    supporting_excerpt: str

    @field_validator("*")
    @classmethod
    def strip_non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("字段不能为空")
        return value


class RagDocumentCandidate(StrictModel):
    plan_id: str
    title: str
    markdown: str

    @field_validator("*")
    @classmethod
    def strip_non_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("字段不能为空")
        return value


class PlanItem(StrictModel):
    plan_id: str
    stage: Literal[
        "sft",
        "rag_documents",
        "rag_evaluation",
        "lora_evaluation",
    ]
    ordinal: int = Field(ge=0)
    split: Literal["train", "val", "test"] | None = None
    category: str
    topic: str
    difficulty: str = ""
    scenario: str = ""
    source_document: str = ""
    seed: int


class AcceptedRecord(StrictModel):
    plan: PlanItem
    data: dict[str, Any]
    accepted_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
    )


class RejectedRecord(StrictModel):
    plan_id: str
    stage: str
    attempt: int
    reasons: list[str]
    raw_preview: str = ""
    quality_rule_version: int = Field(default=1, ge=1)
    rejected_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
    )


class DocumentManifestItem(StrictModel):
    plan_id: str
    path: str
    source_type: Literal["generated", "external"]
    sha256: str
    domain: str = ""
    topic: str = ""
    original_name: str = ""


class RetrievalMetrics(StrictModel):
    recall_at_k: float = Field(ge=0, le=1)
    # 保留旧字段，单相关文档评测集中与 Recall@K 等价。
    hit_at_k: float = Field(ge=0, le=1)
    reciprocal_rank: float = Field(ge=0, le=1)
    excerpt_recall: float = Field(ge=0, le=1)


class AnswerMetrics(StrictModel):
    answer_score: float = Field(ge=0, le=1)
    faithfulness: float = Field(ge=0, le=1)
    token_f1: float = Field(ge=0, le=1)
    rouge_l: float = Field(ge=0, le=1)
    source_support: float = Field(ge=0, le=1)


class JudgeScores(StrictModel):
    correctness: float = Field(ge=0, le=5)
    relevance: float = Field(ge=0, le=5)
    groundedness: float = Field(ge=0, le=5)
    engineering_quality: float = Field(ge=0, le=5)
    reason: str


class ExperimentCaseResult(StrictModel):
    case_index: int
    variant: str
    retrieval_strategy: str = "none"
    reranker_enabled: bool = False
    question: str
    reference_answer: str
    source_document: str
    generated_answer: str = ""
    retrieved_sources: list[str] = Field(default_factory=list)
    retrieval_metrics: RetrievalMetrics | None = None
    answer_metrics: AnswerMetrics | None = None
    judge_scores: JudgeScores | None = None
    latency_ms: int = Field(default=0, ge=0)
    error: str | None = None


class VariantSummary(StrictModel):
    name: str
    retrieval_strategy: str
    reranker_enabled: bool
    case_count: int
    success_rate: float
    retrieval_metrics: dict[str, float] | None
    answer_metrics: dict[str, float] | None
    judge_metrics: dict[str, float] | None
    latency_ms_average: float
    latency_ms_p95: float


class ExperimentReport(StrictModel):
    created_at: str
    mode: Literal["end_to_end", "retrieval_only"]
    evaluation_count: int
    variants: list[VariantSummary]


class QualityIssue(StrictModel):
    severity: Literal["error", "warning"]
    code: str
    message: str
    file: str = ""
    line: int | None = None


class QualityReport(StrictModel):
    created_at: str
    passed: bool
    counts: dict[str, int]
    distributions: dict[str, dict[str, int]]
    duplicate_stats: dict[str, int]
    statistics: dict[str, dict[str, float]]
    rejection_stats: dict[str, Any]
    generation: dict[str, Any]
    api_usage: dict[str, int]
    issues: list[QualityIssue]
