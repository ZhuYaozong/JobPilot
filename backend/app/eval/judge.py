"""LLM-as-judge 评分模块。

用一个独立的 LLM 调用对 agent 回复做"软质量"评分,弥补确定性断言
(tool_called / final_contains 等)只能验证"做没做对"而无法验证"做得好不好"
的空缺。

典型评分维度:专业性 / 中文表达 / 完整性 / 语气等,由 case 作者在 YAML 的
``rubric`` 字段自由定义。

流程:
1. 根据 rubric + 用户原文 + agent 回复 + 工具调用摘要,拼装 judge prompt
2. 调用真实 ``LLMClient.generate_text`` 拿回结构化 JSON
3. 解析成 :class:`JudgeVerdict` 供断言器使用

**Judge LLM 始终调真实 API**——它评估的是 agent 回复质量,不能被 fake 替代。
fake 模式下 runner 会跳过 ``llm_judge`` 断言,不会触碰本模块。
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.llm.client import LLMClient


@dataclass
class JudgeVerdict:
    """Judge LLM 返回的结构化评分。

    ``score`` 是 0.0~1.0 归一化总分(各维度满分加权平均);
    ``aspects`` 是各维度明细;
    ``reasoning`` 是 judge 的整体评语。
    """

    score: float
    aspects: list[dict[str, Any]] = field(default_factory=list)
    reasoning: str = ""


# judge 系统提示——告诉 LLM 它的角色和输出格式
_JUDGE_SYSTEM = """\
你是一个求职 AI 助手的质量评审员。你的任务是根据给定的评分标准(rubric),
对助手的回复做结构化评分。

输出要求:必须输出合法 JSON,格式如下:
{
  "aspects": [
    {"name": "维度名", "score": 3, "max": 5, "reason": "一句话理由"}
  ],
  "reasoning": "整体评语,2-3 句"
}

评分规则:
- 每个维度按 rubric 描述的分制打分(例如 0-5)
- reason 必须具体,指出回复里的实例而非泛泛而谈
- reasoning 给出整体结论
- 只输出 JSON,不要包含 markdown 代码块标记"""


def _build_judge_prompt(
    rubric: str,
    user_text: str,
    final_text: str,
    tool_calls: list[dict[str, Any]],
    context_desc: str | None = None,
) -> str:
    """拼装 judge prompt,包含评分标准和待评估内容。"""
    tool_summary = "无工具调用"
    if tool_calls:
        items = []
        for tc in tool_calls:
            name = tc.get("tool_name", "unknown")
            status = tc.get("status", "unknown")
            items.append(f"  - {name}({status})")
        tool_summary = "\n".join(items)

    parts = [
        _JUDGE_SYSTEM,
        "",
        "--- 评分标准(rubric) ---",
        rubric.strip(),
        "",
        "--- 用户原文 ---",
        user_text,
        "",
    ]
    if context_desc:
        parts.append(f"--- 对话上下文 ---\n{context_desc}\n")
    parts.extend([
        "--- 工具调用摘要 ---",
        tool_summary,
        "",
        "--- 助手回复(待评分) ---",
        final_text or "(空回复)",
    ])
    return "\n".join(parts)


def _parse_verdict(raw: str) -> JudgeVerdict:
    """从 LLM 原始输出解析 JudgeVerdict。

    容错策略:
    - 剥离可能的 markdown 代码块标记(```json ... ```)
    - JSON 解析失败 → 返回 score=0 + 原始文本作为 reasoning
    - aspects 缺失 → 空列表,score 由 reasoning 兜底
    """
    text = raw.strip()
    # 剥离 markdown 代码块
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return JudgeVerdict(score=0.0, reasoning=f"judge 输出 JSON 解析失败: {raw[:300]}")

    aspects = data.get("aspects") or []
    reasoning = data.get("reasoning") or ""

    # 计算归一化总分:各维度 score/max 的平均值
    if aspects:
        ratios = []
        for a in aspects:
            max_val = a.get("max", 5)
            if max_val > 0:
                ratios.append(a.get("score", 0) / max_val)
        score = sum(ratios) / len(ratios) if ratios else 0.0
    else:
        score = 0.0

    return JudgeVerdict(score=score, aspects=aspects, reasoning=reasoning)


async def run_judge(
    rubric: str,
    user_text: str,
    final_text: str,
    tool_calls: list[dict[str, Any]],
    context_desc: str | None = None,
) -> JudgeVerdict:
    """执行一次 judge 评分,返回结构化结果。

    内部新建 ``LLMClient()`` 调真实 API——judge 不受 runner 的 fake patch
    影响,因为 runner 在调本函数时已经退出了 ``_llm_patch`` 上下文。
    """
    prompt = _build_judge_prompt(
        rubric=rubric,
        user_text=user_text,
        final_text=final_text,
        tool_calls=tool_calls,
        context_desc=context_desc,
    )
    client = LLMClient()
    raw = await client.generate_text(prompt)
    return _parse_verdict(raw)
