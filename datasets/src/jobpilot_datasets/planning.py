"""根据配置构建确定性数据生成计划。"""

from __future__ import annotations

import random
from collections.abc import Sequence

from jobpilot_datasets.config import AppConfig
from jobpilot_datasets.models import DocumentManifestItem, PlanItem
from jobpilot_datasets.text_utils import sha256_text, stable_seed


def build_sft_plan(config: AppConfig) -> list[PlanItem]:
    """为每个 split 和任务类型分配严格配额。"""
    plans: list[PlanItem] = []
    ordinal = 0
    for split_index, (split, total) in enumerate(config.lora.splits.items()):
        per_category = total // len(config.lora.task_types)
        split_plans: list[PlanItem] = []
        for category_index, category in enumerate(config.lora.task_types):
            topics = config.lora.topic_catalog[category]
            for category_ordinal in range(per_category):
                plan_id = (
                    f"sft-{split}-{category_index:02d}-{category_ordinal:04d}"
                )
                item_seed = stable_seed(config.seed, plan_id)
                rng = random.Random(item_seed)
                split_plans.append(
                    PlanItem(
                        plan_id=plan_id,
                        stage="sft",
                        ordinal=ordinal,
                        split=split,
                        category=category,
                        topic=topics[category_ordinal % len(topics)],
                        difficulty=rng.choice(config.lora.difficulty_levels),
                        scenario=rng.choice(config.lora.scenarios),
                        seed=item_seed,
                    ),
                )
                ordinal += 1
        # 打乱生成顺序但保留 ordinal，最终导出仍按 ordinal 稳定排序。
        random.Random(config.seed + split_index).shuffle(split_plans)
        plans.extend(split_plans)
    return plans


def build_rag_document_plan(config: AppConfig) -> list[PlanItem]:
    """把约 50 篇文档尽量均匀分配到所有领域。"""
    plans: list[PlanItem] = []
    domain_count = len(config.rag_documents.domains)
    base_count, remainder = divmod(config.rag_documents.total, domain_count)
    ordinal = 0
    for domain_index, domain in enumerate(config.rag_documents.domains):
        count = base_count + (1 if domain_index < remainder else 0)
        topics = config.rag_documents.topic_catalog[domain]
        for topic_ordinal in range(count):
            plan_id = f"ragdoc-{domain_index:02d}-{topic_ordinal:03d}"
            topic = topics[topic_ordinal % len(topics)]
            plans.append(
                PlanItem(
                    plan_id=plan_id,
                    stage="rag_documents",
                    ordinal=ordinal,
                    category=domain,
                    topic=topic,
                    difficulty="工程实践",
                    scenario="技术知识文档",
                    seed=stable_seed(config.seed, plan_id),
                ),
            )
            ordinal += 1
    return plans


def build_lora_evaluation_plan(config: AppConfig) -> list[PlanItem]:
    """构建与 SFT split 分离、类别尽量均衡的独立评测计划。"""
    plans: list[PlanItem] = []
    task_count = len(config.lora.task_types)
    base_count, remainder = divmod(config.lora_evaluation.total, task_count)
    ordinal = 0
    for category_index, category in enumerate(config.lora.task_types):
        count = base_count + (1 if category_index < remainder else 0)
        topics = config.lora.topic_catalog[category]
        for category_ordinal in range(count):
            plan_id = (
                f"loraeval-{category_index:02d}-{category_ordinal:04d}"
            )
            item_seed = stable_seed(config.seed, plan_id)
            rng = random.Random(item_seed)
            plans.append(
                PlanItem(
                    plan_id=plan_id,
                    stage="lora_evaluation",
                    ordinal=ordinal,
                    category=category,
                    topic=topics[
                        (category_ordinal + category_index + 1) % len(topics)
                    ],
                    difficulty=rng.choice(config.lora.difficulty_levels),
                    scenario=rng.choice(config.lora_evaluation.scenarios),
                    seed=item_seed,
                ),
            )
            ordinal += 1
    random.Random(config.seed + 10_000).shuffle(plans)
    return plans


def build_rag_evaluation_plan(
    config: AppConfig,
    documents: Sequence[DocumentManifestItem],
) -> list[PlanItem]:
    """按文档轮转分配问题，确保每篇文档都有覆盖。"""
    if not documents:
        raise ValueError("没有可用于 RAG 评测的数据源文档")
    ordered = sorted(documents, key=lambda item: item.path)
    plans: list[PlanItem] = []
    for ordinal in range(config.rag_evaluation.total):
        document = ordered[ordinal % len(ordered)]
        per_document_index = ordinal // len(ordered)
        source_key = sha256_text(f"{document.sha256}:{document.path}")[:10]
        plan_id = f"rageval-{source_key}-{per_document_index:03d}"
        plans.append(
            PlanItem(
                plan_id=plan_id,
                stage="rag_evaluation",
                ordinal=ordinal,
                category=document.source_type,
                topic=document.topic or document.original_name or document.path,
                scenario="文档依据问答",
                source_document=document.path,
                seed=stable_seed(config.seed, plan_id),
            ),
        )
    return plans


def plan_summary(plans: Sequence[PlanItem]) -> dict[str, object]:
    by_stage: dict[str, int] = {}
    by_split: dict[str, int] = {}
    by_category: dict[str, int] = {}
    for plan in plans:
        by_stage[plan.stage] = by_stage.get(plan.stage, 0) + 1
        if plan.split:
            by_split[plan.split] = by_split.get(plan.split, 0) + 1
        by_category[plan.category] = by_category.get(plan.category, 0) + 1
    return {
        "total": len(plans),
        "by_stage": by_stage,
        "by_split": by_split,
        "by_category": by_category,
    }
