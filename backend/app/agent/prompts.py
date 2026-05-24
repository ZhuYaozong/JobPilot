"""LangGraph workflow 各节点使用的 prompt 构造器。

本模块只负责构造 prompt 文本，不做模型调用和业务判断。
这样 workflow 可以专注状态流转，prompt 也更容易在未来 eval 切片里独立迭代。

切片 4 之后，prompt 同时拼接最近对话 ``conversation_history`` 和长期摘要
``existing_summary``，让 Agent 能跨轮理解“这个岗位”“上一版简历”等指代。
``build_decide_repair_prompt`` 专门处理第一次 decide 输出坏 JSON / 坏 schema 的场景，
它会把上次坏输出和解析错误一起给模型看，只允许一次自修复。``build_summarize_prompt``
则把长对话压缩成未来 decide 可读的短摘要，避免每轮都塞完整 transcript。

工具说明实时从 ``TOOL_REGISTRY`` 拉取，新增工具后不需要手工维护 prompt 里的工具清单。
"""

import json
from typing import Any, Iterable

from app.agent.tools import TOOL_REGISTRY


def _build_tools_section() -> str:
    # 工具说明实时从注册表生成，新增工具后不会忘记同步 prompt 的工具清单。
    parts: list[str] = []
    for name, cls in TOOL_REGISTRY.items():
        args_schema = cls.args_schema.model_json_schema()
        parts.append(
            f"- {name}: {cls.description}\n"
            f"  参数 JSON schema: {json.dumps(args_schema, ensure_ascii=False)}"
        )
    return "\n".join(parts)


def _format_history(history: Iterable[dict[str, str]]) -> str:
    # 把内部 role 映射成中文标签，让模型看到的对话上下文更贴近最终语言。
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
    # 摘要为空时完全不拼接该段，避免 prompt 里出现误导性的空标题。
    if not existing_summary:
        return ""
    return f"\n之前对话的摘要(过早的轮次已被压缩):\n{existing_summary}\n"


def _format_tool_call_history(
    tool_call_history: Iterable[dict[str, Any]],
) -> str:
    """把本轮已经调用过的工具格式化给 decide 节点。

    每条记录包含 ``tool``、``args``、``result``。这里暂时不截断工具结果，确保模型
    观察到完整事实；如果后续生产环境 token 压力变大，可以把这里替换成“保留关键字段 +
    摘要长文本”的序列化器。
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
    # decide prompt 的输出必须是 JSON；workflow 后面会用 Pydantic 再兜底校验。
    tools_section = _build_tools_section()
    summary_section = _format_summary_section(existing_summary)
    history_section = _format_history(history or [])
    tool_history_section = _format_tool_call_history(tool_call_history or [])
    budget_hint = ""
    if iterations_remaining is not None:
        # 把剩余预算显式告诉模型，可以减少最后一次还想继续 call_tool 的概率。
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
- 如果用户要"添加 / 录入 / 帮我加 / 帮我保存"一个**新**岗位或简历(贴了 JD 文本、岗位 URL,
  或一段简历正文),先调 draft_job / draft_resume 起草,不要直接调 create_*。
  拿到草稿后用 respond_directly 把摘要给用户看(公司、岗位、城市、简历标题、要点等),
  让用户确认或要求修改。下一轮用户同意后再调用 create_job / create_resume 落库,
  调用时把 draft_* 返回的 parsed_json 一并传入,避免重复解析。
- 如果用户要 Agent**基于具体简历 / 岗位的细节内容**回答(项目经历、JD 要求、责任、技能等),
  且这些信息**不在对话历史 / 摘要 / 之前工具结果**里 → 调 read_resume / read_job_posting。
  优先级:先 list_user_* 找 id → 再 read_* 拿细节,不要把 list 当 read 用。
- 如果某个简历 / 岗位的 parse_status 是 pending(parsed_json 为 null),而下一步动作工具
  (analyze_match / generate_*)需要 parsed_json → 先调 parse_resume / parse_job_posting
  把它升级到 parsed,再调动作工具。
- 投递记录相关:
  - 用户说"帮我记一下投递了 X""标记成投递了"等创建意图 → create_application
    (先 list_user_* 拿 resume_id 和 job_posting_id)。
  - 用户说"改成 interview""标记成 offer""加个 note"等阶段流转 → update_application_stage
    (先 list_user_applications 拿 application_id)。
- 用户问"我之前的求职信""我准备过的面试材料"等已生成材料 → 先 list_generated_artifacts 查,
  有结果就直接展示(标题、id、时间),**不要**重复调用 generate_* 再生一份。
- **关于 add_knowledge_text(高敏感)**:
  - 用户**明确说**"保存到知识库""帮我记到知识库""把这段加到 X 知识库" 等关键词时才调用。
  - 用户**只是粘贴**公司背景、面试笔记、项目描述,**没说要保存**:用 respond_directly 回应,
    **绝不主动**调 add_knowledge_text。
  - 没指定 knowledge_base_id 时,先 respond_directly 询问要存到哪个库,而不是猜一个 id。
- **关于 write 类工具的必填字段(create_* / draft_* / add_* / update_*)**:
  - 调用前必须确认所有必填字段都从对话/工具历史里拿到了真实值,**绝不**用空串、占位、
    或自己猜的内容凑数。
  - 缺任何必填字段,**先用 respond_directly 自然地向用户追问**那个具体字段,
    例如"好的,请把 JD 文本发过来"或"想保存到哪个知识库?",**不要**先调工具试错。
  - 工具如果返回 `error_class=missing_required_field`(因为模型仍硬调了),
    回复用户时按 message_for_llm 用自然语言追问缺失字段,不要暴露 error_class 这种内部词。
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

    ``tool_call_history`` 是本轮调用过的完整工具列表。prompt 会强调“综合结果”，
    避免模型把每个工具调用按流水账复述给用户。
    """
    # format_response 只负责把工具观察结果转成用户可读中文，不再决定新工具。
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
    # 摘要只存事实和决策，避免把整段聊天原文继续塞回未来 prompt。
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
