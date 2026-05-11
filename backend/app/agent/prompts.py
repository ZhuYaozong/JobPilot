"""System prompts used by the LangGraph workflow nodes.

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
from typing import Iterable

from app.agent.tools import TOOL_REGISTRY


def _build_tools_section() -> str:
    parts: list[str] = []
    for name, cls in TOOL_REGISTRY.items():
        args_schema = cls.args_schema.model_json_schema()
        parts.append(
            f"- {name}: {cls.description}\n"
            f"  args JSON schema: {json.dumps(args_schema, ensure_ascii=False)}"
        )
    return "\n".join(parts)


def _format_history(history: Iterable[dict[str, str]]) -> str:
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
    if not existing_summary:
        return ""
    return f"\n之前对话的摘要(过早的轮次已被压缩):\n{existing_summary}\n"


def build_decide_prompt(
    user_text: str,
    history: Iterable[dict[str, str]] | None = None,
    existing_summary: str | None = None,
) -> str:
    tools_section = _build_tools_section()
    summary_section = _format_summary_section(existing_summary)
    history_section = _format_history(history or [])
    return f"""你是 JobPilot 的求职助手。根据用户消息,决定:
(A) 是否需要调用某个工具来完成任务
(B) 或者直接用文字回复用户

可用工具:
{tools_section}

请严格按以下两种 JSON 之一回复,不要任何其它解释、代码块或前后缀:

需要调用工具:
{{"action": "call_tool", "tool": "<工具名>", "args": {{...参数对象...}}}}

不需要调用工具,直接回复:
{{"action": "respond_directly", "text": "<给用户的话>"}}

判断规则:
- 用户明确给出所需参数(比如 resume_id + job_posting_id)并想要某个工具能完成的事,选 call_tool。
- 用户只是闲聊、问问题或信息不全,选 respond_directly,
  在 text 字段里温和地引导用户提供需要的信息。
- 不要猜测用户没说的 id。
- 如果对话历史/摘要里已经提到过 resume_id / job_posting_id 等关键信息,你可以复用。
{summary_section}
对话历史(最近的在最下面):
{history_section}

本轮用户消息:
{user_text}
"""


def build_decide_repair_prompt(
    user_text: str,
    history: Iterable[dict[str, str]] | None,
    existing_summary: str | None,
    previous_raw_output: str,
    error_description: str,
) -> str:
    """Second-chance prompt after the first decide returned unparseable output."""
    base = build_decide_prompt(user_text, history, existing_summary)
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
    tool_name: str,
    tool_result: dict,
    history: Iterable[dict[str, str]] | None = None,
) -> str:
    result_json = json.dumps(tool_result, ensure_ascii=False, indent=2)
    history_section = _format_history(history or [])
    return f"""你是 JobPilot 的求职助手。刚才你调用了工具 `{tool_name}`,下面是工具返回的结果。
请把结果用自然、简洁的中文回复给用户。规则:
- 如果 ok=true:用 data 内容写一段对用户有用的总结,不要把 JSON 字面值贴回去。
- 如果 ok=false:婉转告知用户出了什么问题,如果可以,基于 message_for_llm 给出
  下一步建议。不要暴露 error_class 等内部字段名。
- 不要复述"我调用了 xxx 工具"这种过程性描述,直接给结论。
- 注意对话历史里的上下文,避免重复已经说过的话。

对话历史(最近的在最下面):
{history_section}

本轮用户消息:
{user_text}

工具结果:
{result_json}
"""


def build_summarize_prompt(history: Iterable[dict[str, str]]) -> str:
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
