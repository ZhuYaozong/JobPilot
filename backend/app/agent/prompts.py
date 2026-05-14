"""System prompts used by the LangGraph workflow nodes.

中文说明：本模块只负责构造 prompt 文本，不做模型调用和业务判断。
这样 workflow 可以专注状态流转，prompt 也更容易在未来 eval 切片里独立迭代。

Keeping prompts in their own module makes them easier to A/B test in a future
evaluation slice and avoids cluttering the workflow code with multi-line
strings.

Slice 4 additions:
- ``conversation_history`` (recent turns) and ``existing_summary`` (long-term
  memory) are stitched into the decide and format_response prompts so the
  agent has multi-turn context.
- ``build_decide_repair_prompt`` runs after the first decide call produced
  garbage. It re-shows the model the previous bad output plus the parser /
  schema error.
- ``build_summarize_prompt`` produces a compact memory summary that future
  decide calls can read instead of the full transcript.

Tool descriptions are pulled live from ``TOOL_REGISTRY`` so adding a tool in a
later slice does not require editing this file.
"""

import json
from typing import Any, Iterable

from app.agent.tools import TOOL_REGISTRY


def _build_tools_section() -> str:
    # 中文说明：工具说明实时从注册表生成，新增工具后不会忘记同步 prompt 的工具清单。
    parts: list[str] = []
    for name, cls in TOOL_REGISTRY.items():
        args_schema = cls.args_schema.model_json_schema()
        parts.append(
            f"- {name}: {cls.description}\n"
            f"  参数 JSON schema: {json.dumps(args_schema, ensure_ascii=False)}"
        )
    return "\n".join(parts)


def _format_history(history: Iterable[dict[str, str]]) -> str:
    # 中文说明：把内部 role 映射成中文标签，让模型看到的对话上下文更贴近最终语言。
    lines: list[str] = []
    for msg in history:
        role = msg.get("role", "user")
        content = (msg.get("content") or "").strip()
        if not content:
            continue
        prefix = {"user": "用户", "assistant": "助手", "system": "系统", "tool": "工具"}.get(
            role, role,
        )
        lines.append(f"[{prefix}] {content}")
    return "\n".join(lines) if lines else "(空)"


def _format_summary_section(existing_summary: str | None) -> str:
    # 中文说明：摘要为空时完全不拼接该段，避免 prompt 里出现误导性的空标题。
    if not existing_summary:
        return ""
    return f"\n之前对话的摘要(过早的轮次已被压缩):\n{existing_summary}\n"


def _format_tool_call_history(
    tool_call_history: Iterable[dict[str, Any]],
) -> str:
    """把本轮已经调用过的工具格式化给 decide 节点。

    Each entry has keys ``tool``, ``args``, ``result``. Results may be large
    structured dicts; we serialise them as JSON without truncation so the
    LLM gets the full observation. If this turns out to push token usage too
    high in production we can switch to a summarising serialiser.
    """
    entries = list(tool_call_history)
    if not entries:
        return "(本轮还没有调用过工具)"
    lines: list[str] = []
    for idx, entry in enumerate(entries, start=1):
        tool = entry.get("tool", "<unknown>")
        args = json.dumps(entry.get("args") or {}, ensure_ascii=False)
        result = json.dumps(entry.get("result") or {}, ensure_ascii=False)
        lines.append(
            f"[{idx}] 工具: {tool}\n    参数: {args}\n    结果: {result}",
        )
    return "\n".join(lines)


def build_decide_prompt(
    user_text: str,
    history: Iterable[dict[str, str]] | None = None,
    existing_summary: str | None = None,
    tool_call_history: Iterable[dict[str, Any]] | None = None,
    iterations_remaining: int | None = None,
) -> str:
    # 中文说明：decide prompt 的输出必须是 JSON；workflow 后面会用 Pydantic 再兜底校验。
    tools_section = _build_tools_section()
    summary_section = _format_summary_section(existing_summary)
    history_section = _format_history(history or [])
    tool_history_section = _format_tool_call_history(tool_call_history or [])
    budget_hint = ""
    if iterations_remaining is not None:
        # 中文说明：把剩余预算显式告诉模型，可以减少最后一次还想继续 call_tool 的概率。
        budget_hint = (
            f"\n本轮剩余工具调用次数: {iterations_remaining}。"
            f"如果剩余次数为 0 或 1,优先选 respond_directly,把目前的信息总结给用户。\n"
        )
    return f"""你是 JobPilot 的求职助手。根据用户消息,决定下一步:
(A) 调用一个工具(进一步查找信息或生成产物)
(B) 或者直接用文字回复用户

可用工具:
{tools_section}

请严格按以下两种 JSON 之一回复,不要任何其它解释、代码块或前后缀:

需要调用工具:
{{"action": "call_tool", "tool": "<工具名>", "args": {{...参数对象...}}}}

不需要调用工具,直接回复:
{{"action": "respond_directly", "text": "<给用户的话>"}}

判断规则:
- 如果用户用名字提到岗位/简历/投递(例如"腾讯的岗位"、"我最新的简历")但你不知道 id,
  优先调用 list_user_jobs / list_user_resumes / list_user_applications 查出来。
- 如果用户问到自己**保存过的资料**才能回答的细节(公司背景、项目经历、面试笔记、
  以前的复盘等),且答案不在对话历史 / 摘要里 → 调用 search_knowledge 检索。
  注意 search_knowledge 是检索用户的**知识库内容**,**不是**岗位/简历元数据。
- 如果本轮上下文提示里选中了知识库,调用 search_knowledge 时使用该知识库 id。
- 拿到 id 后再调用需要 id 的动作工具(analyze_match / generate_cover_letter /
  generate_interview_prep / generate_tailored_resume)。
- 如果当前上下文提示里是"模拟面试"模式:
  - 没有简历和岗位 id 时,直接回复用户先在右侧选择简历和岗位,不要调用工具。
  - 用户要求开始模拟面试且已有简历+岗位 id 时,本轮优先按顺序准备信息:先调用 analyze_match,
    再调用 generate_interview_prep;如果上下文还选了知识库,再调用 search_knowledge 检索公司背景、
    项目经历或面试笔记。最后直接开始第一题。
  - 如果用户正在回答上一题,通常直接给一句具体反馈并继续追问下一题;只有确实缺少资料时才检索知识库。
  - 最终回复要像面试官:简短开场或反馈后,只提出 1 个问题;不要一次性输出完整题库或长篇面试提纲。
- 如果已有足够信息回答用户,选 respond_directly;不要重复调用同样参数的同一个工具。
- 不要猜测用户没说的字段。
- 如果对话摘要 / 历史 / 工具结果里已经包含某个 id,直接使用。
{budget_hint}{summary_section}
对话历史(最近的在最下面):
{history_section}

本轮已经调用过的工具(按时间顺序):
{tool_history_section}

本轮用户消息:
{user_text}
"""


def build_decide_repair_prompt(
    user_text: str,
    history: Iterable[dict[str, str]] | None,
    existing_summary: str | None,
    previous_raw_output: str,
    error_description: str,
    tool_call_history: Iterable[dict[str, Any]] | None = None,
    iterations_remaining: int | None = None,
) -> str:
    """第一次 decide 输出不可解析内容后的唯一修复 prompt。"""
    base = build_decide_prompt(
        user_text,
        history,
        existing_summary,
        tool_call_history=tool_call_history,
        iterations_remaining=iterations_remaining,
    )
    return f"""{base}

# 重要 — 修正之前的错误回复
你上一次的回复无法解析,具体问题:
{error_description}

你上次输出的原始内容(供你参考,不要再输出格式错误的版本):
---
{previous_raw_output}
---

请重新输出**严格的 JSON**,只能是上面规定的两种格式之一。这是唯一一次重试机会。
"""


def build_format_response_prompt(
    user_text: str,
    tool_call_history: Iterable[dict[str, Any]],
    history: Iterable[dict[str, str]] | None = None,
) -> str:
    """构造最终回复 prompt。

    ``tool_call_history`` is the full list of tools invoked this turn (one or
    more). The prompt emphasises that the LLM should synthesise across all of
    them rather than narrating each call.
    """
    # 中文说明：format_response 只负责把工具观察结果转成用户可读中文，不再决定新工具。
    history_section = _format_history(history or [])
    tool_history_section = _format_tool_call_history(tool_call_history)
    return f"""你是 JobPilot 的求职助手。本轮你为了回答用户的问题,调用了下面这些工具(可能不止一个)。
请把所有结果综合成一段自然、简洁的中文回复。规则:
- 综合所有工具结果,直接给用户能用的结论;不要逐个工具流水账。
- 如果某个工具结果 ok=false:基于 message_for_llm 婉转告诉用户出了什么、下一步可以怎么做。
  不要暴露 error_class 这种内部字段名。
- 不要把 JSON 字面值贴回去。
- 不要说"我调用了 xxx 工具"这种过程性描述。
- 注意对话历史上下文,不要重复说过的话。
- 用户问题里指代不清的(比如"这个岗位")就用你查到的具体名字来指代,让用户知道你抓到的是哪个。
- 如果本轮用户消息包含"模式:模拟面试",回复要进入交互式面试状态:
  简短开场或基于用户上一轮回答给一句反馈,然后只问 1 个面试问题。
  不要把完整面试提纲、题库或工具结果一次性贴给用户。

对话历史(最近的在最下面):
{history_section}

本轮的工具调用与结果(按时间顺序):
{tool_history_section}

本轮用户消息:
{user_text}
"""


def build_summarize_prompt(history: Iterable[dict[str, str]]) -> str:
    # 中文说明：摘要只存事实和决策，避免把整段聊天原文继续塞回未来 prompt。
    history_section = _format_history(history)
    return f"""你是 JobPilot 的对话摘要生成器。下面是一段较长的求职助手对话历史。
请把它压缩成一段**简洁的中文摘要**,捕获:
- 用户关心的目标(求职方向、岗位、简历版本等)
- 已经讨论过的关键事实(resume_id、job_posting_id、application_record_id、
  match 得分、已生成的求职信/面试材料等)
- 任何未完成的待办或下一步动作

要求:
- 只输出纯文本摘要,不要用项目符号、不要 Markdown,字数控制在 200 字以内。
- 用第三人称("用户"、"助手")。
- 不要复述每一句话,聚焦事实和决策。

对话历史:
{history_section}
"""
