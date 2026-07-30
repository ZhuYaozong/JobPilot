"""生成阶段的内容质量门禁。"""

from __future__ import annotations

import re
from pathlib import Path

from jobpilot_datasets.config import AppConfig
from jobpilot_datasets.models import RagEvalItem, SFTItem
from jobpilot_datasets.text_utils import (
    normalize_for_match,
    visible_char_count,
)


ENGINEERING_SIGNAL_GROUPS: dict[str, tuple[str, ...]] = {
    "implementation": (
        "接口",
        "模块",
        "服务",
        "流程",
        "步骤",
        "策略",
        "方案",
        "方法",
        "算法",
        "公式",
        "规则",
        "计算",
        "匹配",
        "折算",
        "数据库",
        "队列",
        "缓存",
        "配置",
        "代码",
        "部署",
        "索引",
        "模型",
        "参数",
    ),
    "reliability": (
        "超时",
        "重试",
        "幂等",
        "降级",
        "熔断",
        "回滚",
        "回退",
        "兜底",
        "失败",
        "异常",
        "容灾",
        "校验",
    ),
    "measurement": (
        "指标",
        "延迟",
        "召回率",
        "准确率",
        "吞吐",
        "P95",
        "P99",
        "命中率",
        "通过率",
        "邀约率",
        "错误率",
        "响应时间",
        "阈值",
        "QPS",
        "测试",
        "数据",
        "成本",
    ),
    "tradeoff": (
        "取舍",
        "权衡",
        "相比",
        "代价",
        "优先",
        "适合",
        "缺点",
        "风险",
        "平衡",
    ),
    "operations": (
        "监控",
        "日志",
        "告警",
        "链路",
        "灰度",
        "压测",
        "审计",
        "版本",
    ),
}

PROHIBITED_PATTERNS = (
    "作为一个ai",
    "作为ai",
    "无法提供",
    "todo",
    "待补充",
    "这里填写",
)


def validate_sft_item(item: SFTItem, config: AppConfig) -> list[str]:
    errors: list[str] = []
    instruction_length = visible_char_count(item.instruction)
    answer_length = visible_char_count(item.output)
    if not (
        config.lora.instruction_min_chars
        <= instruction_length
        <= config.lora.instruction_max_chars
    ):
        errors.append(
            f"instruction 有效长度 {instruction_length} 不在 "
            f"{config.lora.instruction_min_chars}~"
            f"{config.lora.instruction_max_chars}",
        )
    if not (
        config.lora.answer_min_chars
        <= answer_length
        <= config.lora.answer_max_chars
    ):
        errors.append(
            f"output 有效长度 {answer_length} 不在 "
            f"{config.lora.answer_min_chars}~{config.lora.answer_max_chars}",
        )

    normalized_output = normalize_for_match(item.output)
    matched_groups = sum(
        1
        for keywords in ENGINEERING_SIGNAL_GROUPS.values()
        if any(normalize_for_match(keyword) in normalized_output for keyword in keywords)
    )
    # 系数、百分比、时延和年限等可量化参数本身也是工程度量信号。
    if not any(
        normalize_for_match(keyword) in normalized_output
        for keyword in ENGINEERING_SIGNAL_GROUPS["measurement"]
    ) and re.search(
        r"(?:\d+(?:\.\d+)?\s*(?:%|ms|s|秒|分钟|小时|天|年|倍|分|条|次))"
        r"|(?:[<>≤≥=]\s*\d+(?:\.\d+)?)",
        item.output,
        flags=re.IGNORECASE,
    ):
        matched_groups += 1
    if matched_groups < config.quality.minimum_engineering_signal_groups:
        errors.append(
            f"工程实践信号只有 {matched_groups} 组，要求至少 "
            f"{config.quality.minimum_engineering_signal_groups} 组",
        )
    lowered = item.output.lower()
    if any(pattern in lowered for pattern in PROHIBITED_PATTERNS):
        errors.append("output 包含占位或空泛表达")
    return errors


def validate_rag_document(markdown: str, config: AppConfig) -> list[str]:
    errors: list[str] = []
    length = visible_char_count(markdown, strip_markdown=True)
    if not (
        config.rag_documents.min_chars
        <= length
        <= config.rag_documents.max_chars
    ):
        errors.append(
            f"文档有效长度 {length} 不在 "
            f"{config.rag_documents.min_chars}~{config.rag_documents.max_chars}",
        )
    if not re.search(r"(?m)^#\s+\S+", markdown):
        errors.append("缺少一级标题")
    for section in ("概念", "原理", "实践案例"):
        if not re.search(rf"(?m)^##\s+{re.escape(section)}\s*$", markdown):
            errors.append(f"缺少“## {section}”章节")
    lowered = markdown.lower()
    if any(pattern in lowered for pattern in PROHIBITED_PATTERNS):
        errors.append("文档包含占位或空泛表达")
    return errors


def validate_rag_eval_item(
    item: RagEvalItem,
    source_path: Path,
    source_content: str,
    config: AppConfig,
) -> list[str]:
    errors: list[str] = []
    answer_length = visible_char_count(item.answer)
    excerpt_length = visible_char_count(item.supporting_excerpt)
    if not (
        config.rag_evaluation.answer_min_chars
        <= answer_length
        <= config.rag_evaluation.answer_max_chars
    ):
        errors.append(
            f"answer 有效长度 {answer_length} 不在 "
            f"{config.rag_evaluation.answer_min_chars}~"
            f"{config.rag_evaluation.answer_max_chars}",
        )
    if not (
        config.rag_evaluation.excerpt_min_chars
        <= excerpt_length
        <= config.rag_evaluation.excerpt_max_chars
    ):
        errors.append(
            f"supporting_excerpt 有效长度 {excerpt_length} 不在 "
            f"{config.rag_evaluation.excerpt_min_chars}~"
            f"{config.rag_evaluation.excerpt_max_chars}",
        )
    if normalize_for_match(item.supporting_excerpt) not in normalize_for_match(
        source_content,
    ):
        errors.append("supporting_excerpt 不是源文档中的连续原文")
    if not source_path.exists():
        errors.append("source_document 不存在")
    return errors
