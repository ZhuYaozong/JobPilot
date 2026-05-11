"""System prompts used by the LangGraph workflow nodes.

Keeping prompts in their own module makes them easier to A/B test in a future
evaluation slice and avoids cluttering the workflow code with multi-line
strings.

The `decide` prompt asks the model to emit strict JSON. The `format_response`
prompt asks for natural-language text. Tool descriptions are pulled live from
``TOOL_REGISTRY`` so adding a tool in a later slice does not require editing
this file.
"""

import json

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


def build_decide_prompt(user_text: str) -> str:
    tools_section = _build_tools_section()
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
- 用户明确给出 resume_id 和 job_posting_id 并想要匹配分析,选 call_tool。
- 用户只是闲聊、问问题或信息不全(比如没有 resume_id),选 respond_directly,
  在 text 字段里温和地引导用户提供需要的信息。
- 不要猜测用户没说的 id。

用户消息:
{user_text}
"""


def build_format_response_prompt(
    user_text: str,
    tool_name: str,
    tool_result: dict,
) -> str:
    result_json = json.dumps(tool_result, ensure_ascii=False, indent=2)
    return f"""你是 JobPilot 的求职助手。刚才你调用了工具 `{tool_name}`,下面是工具返回的结果。
请把结果用自然、简洁的中文回复给用户。规则:
- 如果 ok=true:用 data 内容写一段对用户有用的总结,不要把 JSON 字面值贴回去。
- 如果 ok=false:婉转告知用户出了什么问题,如果可以,基于 message_for_llm 给出
  下一步建议。不要暴露 error_class 等内部字段名。
- 不要复述"我调用了 xxx 工具"这种过程性描述,直接给结论。

原始用户消息:
{user_text}

工具结果:
{result_json}
"""
