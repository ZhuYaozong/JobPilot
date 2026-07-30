from jobpilot_datasets.models import RagEvalItem, SFTItem
from jobpilot_datasets.validation import (
    validate_rag_eval_item,
    validate_sft_item,
)


def test_sft_requires_engineering_details(test_config) -> None:
    item = SFTItem(
        instruction="请说明如何设计一个稳定的模型服务？",
        input="",
        output="这个问题需要综合考虑，选择合适的方法即可。" * 8,
    )
    errors = validate_sft_item(item, test_config)
    assert any("工程实践信号" in error for error in errors)


def test_sft_accepts_formula_and_numeric_engineering_details(test_config) -> None:
    item = SFTItem(
        instruction="请说明如何折算候选人的跨领域工作经验？",
        input="候选人有3年服务端和2年Android经验。",
        output=(
            "我采用分段折算规则：服务端经验权重1.0，Android经验权重0.5，"
            "因此有效年限为3+2×0.5=4年。若Android项目包含服务端接口设计，"
            "经项目证据核验后可把系数调到0.8；只负责UI则不折算。"
            "上线前用历史录用数据回放，比较人工复核一致率并据此调整阈值。"
        ),
    )
    assert validate_sft_item(item, test_config) == []


def test_rag_excerpt_must_exist_in_source(test_config, tmp_path) -> None:
    source = tmp_path / "source.md"
    source.write_text("# 文档\n真实证据只在这里。", encoding="utf-8")
    item = RagEvalItem(
        question="系统如何处理失败？",
        answer="系统通过超时、重试和降级处理失败，并记录监控指标用于定位问题。",
        source_document="source.md",
        supporting_excerpt="文档中不存在的证据片段",
    )
    errors = validate_rag_eval_item(item, source, source.read_text(encoding="utf-8"), test_config)
    assert any("不是源文档" in error for error in errors)
