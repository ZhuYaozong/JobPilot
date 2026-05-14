"""JobPilot Assistant 的 LangGraph 编排层。

这里是 JobPilot Assistant 的编排层，只决定“下一步做什么”和
“工具结果如何回到模型”。数据库会话、用户对象和业务写入都通过闭包或 Tool
Adapter 进入，不放进 LangGraph state，避免异步 ORM 对象被序列化或跨节点误用。

切片 5 引入 ReAct 风格的多工具循环：节点仍然是 ``decide``、``call_tool``、
``format_response``、``maybe_summarize``，但 ``call_tool`` 执行完会回到
``decide``，让模型观察工具结果后决定是否继续调用工具。``decide`` 会同时看到
``tool_call_history`` 和本轮剩余工具预算；如果预算耗尽，即使模型还想继续调用
工具，也会被强制路由到 ``format_response``，把已经拿到的信息收束给用户。

图结构如下：

    START
      ↓
    decide ──┬── action="call_tool" 且还有预算 ──→ call_tool ──→ decide  (循环)
             │
             ├── action="respond_directly" ──→ format_response ──→ maybe_summarize ──→ END
             ├── 预算耗尽但 action="call_tool" ──→ format_response ──→ ...
             ├── decide 输出格式坏且仍有修复机会 ──→ decide  (自修复)
             └── 修复机会耗尽 ──→ END  (写入 decide_error_class)

闭包里的 ``db``、``current_user``、``agent_run_id`` 只在节点函数内部使用。
state 只保存 JSON 可序列化数据；``tool_call_history`` 使用 ``operator.add``
作为 LangGraph reducer，使每次 ``call_tool`` 返回的新记录追加到历史中，而不会
覆盖之前的工具调用。
"""

import operator
from typing import Annotated, Any, Awaitable, Callable, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.prompts import (
    build_decide_prompt,
    build_decide_repair_prompt,
    build_format_response_prompt,
    build_summarize_prompt,
)
from app.agent.tool_adapter import ToolContext, ToolValidationError
from app.agent.tools import TOOL_REGISTRY
from app.llm.client import LLMClient, LLMClientError, LLMConfigError
from app.llm.json_utils import load_llm_json
from app.models.user import User

# 流式接口会注入这个回调，把工作流内部阶段转成 SSE 事件；非流式接口传 None。
# ``event_type`` 当前包括 phase、tool_call_started、tool_call_completed。
# ``data`` 必须保持 JSON 可序列化，方便 /assistant/run-stream 直接写成 SSE 帧。
EventEmitter = Callable[[str, dict[str, Any]], Awaitable[None]]


# ReAct 循环的硬上限，防止模型在工具间无限来回调用。
# prompt 会告诉模型剩余工具预算，让模型尽量主动收束；这里的常量是最后的保险丝。
MAX_TOOL_ITERATIONS = 3

# 消息数达到阈值后才压缩摘要，避免每轮都消耗一次额外 LLM 调用。
# 计数时会把当前轮即将写入的用户消息和助手消息也算进去，所以阈值代表本轮结束后的规模。
SUMMARIZE_MESSAGE_THRESHOLD = 20


class AgentState(TypedDict, total=False):
    # state 必须保持 JSON-serializable；AsyncSession/User 不允许放进来。
    # 调用方在 invoke 之前填充这些输入字段。
    user_id: int
    conversation_id: int
    user_message_id: int
    user_text: str
    agent_run_id: int
    conversation_history: list[dict[str, str]]
    existing_summary: str | None
    message_count_before_user: int
    selected_knowledge_base_id: int | None

    # decide 节点的结构化输出，以及坏输出修复轮需要的临时信息。
    action: Literal["call_tool", "respond_directly"]
    tool_name: str | None
    tool_args: dict[str, Any] | None
    direct_text: str | None
    decide_repair_attempts: int
    decide_last_raw_output: str | None
    decide_last_error: str | None

    # ReAct 累加器。``operator.add`` reducer 会把每次 call_tool 返回的一条记录追加进来。
    tool_call_history: Annotated[list[dict[str, Any]], operator.add]
    iteration_count: int

    # format_response 节点生成的最终回复。
    final_text: str

    # maybe_summarize 节点生成的新摘要，或摘要失败原因。
    new_summary: str | None
    summary_error: str | None

    # 无法在图内自修复的硬失败信号，由调用方写入 AgentRun。
    decide_error_class: str | None
    decide_error_detail: str | None


class _DecideEnvelope(BaseModel):
    """decide 节点要求模型输出的严格 JSON 外壳，防止 prompt 漂移后静默误执行。"""

    action: Literal["call_tool", "respond_directly"]
    tool: str | None = None
    args: dict[str, Any] | None = None
    text: str | None = None


class WorkflowDecideError(Exception):
    """工作流遇到应直接标记 AgentRun 失败的错误时抛出。

    目前主要用于 LLM 配置缺失、网络失败或 format_response 阶段失败。
    decide 阶段的 JSON / Pydantic 输出错误会先走 state 内的修复路径，给模型一次
    自我纠错机会；只有修复仍失败时，才通过 ``decide_error_class`` 结束图。
    """

    def __init__(self, error_class: str, detail: str) -> None:
        super().__init__(f"workflow failed ({error_class}): {detail}")
        self.error_class = error_class
        self.detail = detail


def build_workflow(
    db: AsyncSession,
    current_user: User,
    agent_run_id: int,
    llm_client: LLMClient | None = None,
    emit_event: EventEmitter | None = None,
):
    """为单次请求编译一个新的 LangGraph workflow。

    ``emit_event`` 会在阶段切换、工具开始和工具结束时被调用，流式接口据此展示
    “正在思考”“正在查询”等状态；非流式接口传 None，事件会被丢弃，保持旧的
    一次性响应契约。
    """

    client = llm_client or LLMClient()

    async def emit(event_type: str, data: dict[str, Any]) -> None:
        if emit_event is None:
            return
        try:
            await emit_event(event_type, data)
        except Exception:  # noqa: BLE001 — emit must never crash the workflow
            # 进度事件只是 UI 增强，发送失败不能影响 Agent 主流程。
            pass

    async def decide_node(state: AgentState) -> dict[str, Any]:
        # decide 节点只产出“调用工具”或“直接回复”的结构化决策，不做业务写入。
        attempts = int(state.get("decide_repair_attempts") or 0)
        iterations_used = int(state.get("iteration_count") or 0)
        await emit(
            "phase",
            {
                "phase": "deciding",
                "iteration": iterations_used,
                "repair_attempt": attempts,
            },
        )
        history = state.get("conversation_history") or []
        existing_summary = state.get("existing_summary")
        tool_history = state.get("tool_call_history") or []
        iterations_remaining = max(MAX_TOOL_ITERATIONS - iterations_used, 0)

        if attempts == 0:
            # 第一次决策用常规 prompt；修复轮会携带上次坏输出和解析错误。
            prompt = build_decide_prompt(
                state["user_text"],
                history=history,
                existing_summary=existing_summary,
                tool_call_history=tool_history,
                iterations_remaining=iterations_remaining,
            )
        else:
            prompt = build_decide_repair_prompt(
                state["user_text"],
                history=history,
                existing_summary=existing_summary,
                previous_raw_output=state.get("decide_last_raw_output") or "",
                error_description=state.get("decide_last_error") or "unknown error",
                tool_call_history=tool_history,
                iterations_remaining=iterations_remaining,
            )

        try:
            raw = await client.generate_text(prompt)
        except LLMConfigError as exc:
            raise WorkflowDecideError("llm_config_missing", str(exc)) from exc
        except LLMClientError as exc:
            raise WorkflowDecideError("llm_unavailable", str(exc)) from exc

        try:
            parsed = load_llm_json(raw)
        except ValueError as exc:
            # 模型输出不是 JSON 时不立刻失败，先给一次 repair 机会。
            error = f"output is not valid JSON: {exc}"
            return _decide_failure(attempts, raw, error)

        try:
            envelope = _DecideEnvelope.model_validate(parsed)
        except ValidationError as exc:
            error = f"JSON did not match required schema: {exc}"
            return _decide_failure(attempts, raw, error)

        if envelope.action == "call_tool":
            if envelope.tool not in TOOL_REGISTRY:
                # 工具名不在注册表中通常是模型幻觉，也走 repair 路径。
                error = f"tool {envelope.tool!r} is not registered"
                return _decide_failure(attempts, raw, error)
            return {
                "action": "call_tool",
                "tool_name": envelope.tool,
                "tool_args": envelope.args or {},
                "decide_last_raw_output": None,
                "decide_last_error": None,
            }

        return {
            "action": "respond_directly",
            "direct_text": envelope.text or "",
            "decide_last_raw_output": None,
            "decide_last_error": None,
        }

    async def call_tool_node(state: AgentState) -> dict[str, Any]:
        # call_tool 节点统一走 Tool Adapter，因此这里不直接接触业务 service。
        tool_name = state["tool_name"]
        assert tool_name is not None
        iteration = int(state.get("iteration_count") or 0) + 1
        await emit(
            "tool_call_started",
            {"tool_name": tool_name, "iteration": iteration},
        )
        tool_cls = TOOL_REGISTRY[tool_name]
        ctx = ToolContext(
            db=db,
            current_user=current_user,
            agent_run_id=agent_run_id,
        )
        args = dict(state.get("tool_args") or {})
        selected_knowledge_base_id = state.get("selected_knowledge_base_id")
        if tool_name == "search_knowledge" and selected_knowledge_base_id is not None:
            # UI 选中的知识库是强约束，不能只依赖 LLM 自觉传参或不传错参。
            args["knowledge_base_id"] = selected_knowledge_base_id
        try:
            result = await tool_cls().invoke(args, ctx)
        except ToolValidationError:
            # 参数 schema 错误通常是模型可修复错误；这里造一条 ok=false 的工具观察，
            # 让 format_response 即使没有真实工具结果，也能向用户解释失败原因和下一步。
            result = {
                "ok": False,
                "error_class": "tool_args_invalid",
                "message_for_llm": (
                    "工具参数没有通过 schema 校验。请让用户补充或澄清必要信息，"
                    "并保留字段名、工具名和枚举值的英文写法。"
                ),
                "user_facing_detail": "工具参数未通过校验。",
            }

        await emit(
            "tool_call_completed",
            {
                "tool_name": tool_name,
                "iteration": iteration,
                "ok": bool(result.get("ok", True)),
                "error_class": result.get("error_class"),
            },
        )

        return {
            "tool_call_history": [
                {"tool": tool_name, "args": args, "result": result},
            ],
            "iteration_count": iteration,
            # 清掉本次工具动作的临时槽位，避免下一轮 decide 看到旧 tool_name / tool_args。
            "tool_name": None,
            "tool_args": None,
        }

    async def format_response_node(state: AgentState) -> dict[str, Any]:
        history = state.get("conversation_history") or []

        if state.get("action") == "respond_directly":
            # 直接回复路径不再二次调用模型，使用 decide 节点给出的 text。
            return {"final_text": (state.get("direct_text") or "").strip()}

        await emit("phase", {"phase": "formatting"})

        # 到这里有两种情况：工具调用后模型决定收束，或者预算耗尽被迫收束。
        # 无论哪种，都让 format_response 基于当前工具历史生成一段可读结论。
        tool_history = state.get("tool_call_history") or []
        prompt = build_format_response_prompt(
            user_text=state["user_text"],
            tool_call_history=tool_history,
            history=history,
        )
        try:
            text = await client.generate_text(prompt)
        except (LLMConfigError, LLMClientError) as exc:
            raise WorkflowDecideError("format_response_llm_failed", str(exc)) from exc
        return {"final_text": text.strip()}

    async def maybe_summarize_node(state: AgentState) -> dict[str, Any]:
        # 摘要写入是“尽力而为”的记忆优化，失败不会让本轮对话失败。
        # 当前用户消息已经持久化，助手消息会在 graph 返回后由调用方写入；这里先把两条都
        # 计入阈值，确保判断的是本轮结束后的真实对话长度。
        message_count_after_turn = int(state.get("message_count_before_user") or 0) + 2
        if message_count_after_turn < SUMMARIZE_MESSAGE_THRESHOLD:
            return {}

        await emit("phase", {"phase": "summarizing"})

        history = list(state.get("conversation_history") or [])
        history.append({"role": "user", "content": state["user_text"]})
        history.append({"role": "assistant", "content": state.get("final_text") or ""})

        prompt = build_summarize_prompt(history)
        try:
            text = await client.generate_text(prompt)
        except (LLMConfigError, LLMClientError) as exc:
            return {"summary_error": f"summary_llm_failed: {exc}"}

        new_summary = text.strip()
        if not new_summary:
            return {"summary_error": "summary_llm_returned_empty"}
        return {"new_summary": new_summary}

    def route_after_decide(state: AgentState) -> str:
        if state.get("decide_error_class"):
            return END
        if state.get("decide_last_error"):
            # 第一次 decide 输出坏 JSON / 坏 schema 时，回到 decide 自修复一次。
            return "decide"  # repair self-loop
        if state.get("action") == "call_tool":
            iterations_used = int(state.get("iteration_count") or 0)
            if iterations_used >= MAX_TOOL_ITERATIONS:
                # 预算耗尽时不再调用工具，直接用已收集的信息合成回复。
                return "format_response"
            return "call_tool"
        return "format_response"

    def route_after_call_tool(state: AgentState) -> str:
        # 每次工具调用后都让模型重新观察结果，决定继续查、继续写，还是收束回复。
        return "decide"

    workflow: StateGraph = StateGraph(AgentState)
    workflow.add_node("decide", decide_node)
    workflow.add_node("call_tool", call_tool_node)
    workflow.add_node("format_response", format_response_node)
    workflow.add_node("maybe_summarize", maybe_summarize_node)

    workflow.add_edge(START, "decide")
    workflow.add_conditional_edges(
        "decide",
        route_after_decide,
        {
            "decide": "decide",
            "call_tool": "call_tool",
            "format_response": "format_response",
            END: END,
        },
    )
    workflow.add_conditional_edges(
        "call_tool",
        route_after_call_tool,
        {"decide": "decide"},
    )
    workflow.add_edge("format_response", "maybe_summarize")
    workflow.add_edge("maybe_summarize", END)

    return workflow.compile()


def _decide_failure(
    previous_attempts: int,
    raw_output: str,
    error: str,
) -> dict[str, Any]:
    """集中处理 decide 节点的失败状态。

    如果还有修复预算，就把坏输出和错误原因塞回 state，让下一次 decide 构造修复
    prompt；如果修复预算已用完，就写入硬失败字段，让图直接结束并交给调用方标记
    AgentRun 失败。
    """
    if previous_attempts == 0:
        return {
            "decide_repair_attempts": 1,
            "decide_last_raw_output": raw_output,
            "decide_last_error": error,
        }
    return {
        "decide_error_class": "decide_repair_failed",
        "decide_error_detail": (
            f"both decide attempts produced unusable output."
            f" last_error={error}; last_raw={raw_output!r}"
        ),
    }
