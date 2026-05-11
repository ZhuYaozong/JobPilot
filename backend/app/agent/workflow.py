"""LangGraph workflow for the assistant.

Three nodes: ``decide`` → optional ``call_tool`` → ``format_response``.

The graph state intentionally carries only serialisable fields (ints, strings,
dicts). The AsyncSession and current User are passed to nodes via closures
built at compile time, so the state can later be persisted or streamed without
extra machinery.

Slice 3 keeps this graph deliberately small:

- ``decide`` calls the LLM once and parses a strict JSON envelope. If the LLM
  produces unparseable output we **do not** retry — that repair loop is slated
  for slice 4. A single retry happens only when the LLM ignores instructions
  badly enough to wrap the JSON in a markdown fence; the existing
  ``load_llm_json`` helper handles that case.
- ``call_tool`` is a thin shim over ``BaseTool.invoke``. Business errors flow
  through as ``tool_result.ok == False`` and continue into ``format_response``
  so the LLM can turn them into user-friendly text. System errors propagate as
  ``ToolSystemError`` and are caught by the caller (assistant_service), which
  marks the AgentRun as failed.
- ``format_response`` performs a second LLM call to turn structured output
  into a natural-language reply.
"""

from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.prompts import build_decide_prompt, build_format_response_prompt
from app.agent.tool_adapter import ToolContext, ToolValidationError
from app.agent.tools import TOOL_REGISTRY
from app.llm.client import LLMClient, LLMClientError, LLMConfigError
from app.llm.json_utils import load_llm_json
from app.models.user import User


class AgentState(TypedDict, total=False):
    # Inputs (populated by the caller before invoke).
    user_id: int
    conversation_id: int
    user_message_id: int
    user_text: str
    agent_run_id: int

    # `decide` node output.
    action: Literal["call_tool", "respond_directly"]
    tool_name: str | None
    tool_args: dict[str, Any] | None
    direct_text: str | None

    # `call_tool` node output.
    tool_result: dict[str, Any] | None

    # `format_response` node output.
    final_text: str

    # Soft-failure signalling — populated only when the decide LLM produces
    # unrecoverable garbage. assistant_service treats this as a system error.
    decide_error_class: str | None
    decide_error_detail: str | None


class _DecideEnvelope(BaseModel):
    """Strict shape we ask the decide LLM to emit. Pydantic catches drift."""

    action: Literal["call_tool", "respond_directly"]
    tool: str | None = None
    args: dict[str, Any] | None = None
    text: str | None = None


class WorkflowDecideError(Exception):
    """Raised when the `decide` node fails in a way that should fail the run.

    Currently only fired for LLM config / network errors; JSON / Pydantic
    failures are surfaced via state["decide_error_class"] so a future slice
    can introduce a repair loop without changing the exception contract.
    """

    def __init__(self, error_class: str, detail: str) -> None:
        super().__init__(f"decide node failed ({error_class}): {detail}")
        self.error_class = error_class
        self.detail = detail


def build_workflow(
    db: AsyncSession,
    current_user: User,
    agent_run_id: int,
    llm_client: LLMClient | None = None,
):
    """Compile a fresh LangGraph workflow for a single request.

    The graph is bound to ``db``, ``current_user``, and ``agent_run_id`` via
    closures, so a workflow instance is single-use. The compiled graph is
    returned by this function so callers can ``await graph.ainvoke(...)``.
    """

    client = llm_client or LLMClient()

    async def decide_node(state: AgentState) -> dict[str, Any]:
        prompt = build_decide_prompt(state["user_text"])
        try:
            raw = await client.generate_text(prompt)
        except LLMConfigError as exc:
            raise WorkflowDecideError("llm_config_missing", str(exc)) from exc
        except LLMClientError as exc:
            raise WorkflowDecideError("llm_unavailable", str(exc)) from exc

        try:
            parsed = load_llm_json(raw)
        except ValueError as exc:
            return {
                "decide_error_class": "decide_output_not_json",
                "decide_error_detail": f"raw={raw!r}; err={exc}",
            }

        try:
            envelope = _DecideEnvelope.model_validate(parsed)
        except ValidationError as exc:
            return {
                "decide_error_class": "decide_output_schema_mismatch",
                "decide_error_detail": str(exc),
            }

        if envelope.action == "call_tool":
            if envelope.tool not in TOOL_REGISTRY:
                return {
                    "decide_error_class": "decide_chose_unknown_tool",
                    "decide_error_detail": f"tool={envelope.tool!r} not registered",
                }
            return {
                "action": "call_tool",
                "tool_name": envelope.tool,
                "tool_args": envelope.args or {},
            }

        return {
            "action": "respond_directly",
            "direct_text": envelope.text or "",
        }

    async def call_tool_node(state: AgentState) -> dict[str, Any]:
        tool_name = state["tool_name"]
        assert tool_name is not None
        tool_cls = TOOL_REGISTRY[tool_name]
        ctx = ToolContext(
            db=db,
            current_user=current_user,
            agent_run_id=agent_run_id,
        )
        try:
            result = await tool_cls().invoke(state.get("tool_args") or {}, ctx)
        except ToolValidationError:
            # Slice 3 has no repair loop; treat as a soft failure and let
            # format_response apologise to the user instead of crashing.
            return {
                "tool_result": {
                    "ok": False,
                    "error_class": "tool_args_invalid",
                    "message_for_llm": (
                        "The arguments provided to the tool failed schema "
                        "validation. Ask the user to clarify what they meant."
                    ),
                    "user_facing_detail": "Tool arguments failed validation.",
                },
            }
        return {"tool_result": result}

    async def format_response_node(state: AgentState) -> dict[str, Any]:
        if state.get("action") == "respond_directly":
            return {"final_text": state.get("direct_text") or ""}

        tool_name = state.get("tool_name") or ""
        tool_result = state.get("tool_result") or {}
        prompt = build_format_response_prompt(
            user_text=state["user_text"],
            tool_name=tool_name,
            tool_result=tool_result,
        )
        try:
            text = await client.generate_text(prompt)
        except (LLMConfigError, LLMClientError) as exc:
            raise WorkflowDecideError("format_response_llm_failed", str(exc)) from exc
        return {"final_text": text.strip()}

    def route_after_decide(state: AgentState) -> str:
        if state.get("decide_error_class"):
            # Bail out: assistant_service will look at the state and treat
            # decide_error_class as a system-level failure.
            return END
        if state.get("action") == "call_tool":
            return "call_tool"
        return "format_response"

    workflow: StateGraph = StateGraph(AgentState)
    workflow.add_node("decide", decide_node)
    workflow.add_node("call_tool", call_tool_node)
    workflow.add_node("format_response", format_response_node)

    workflow.add_edge(START, "decide")
    workflow.add_conditional_edges(
        "decide",
        route_after_decide,
        {
            "call_tool": "call_tool",
            "format_response": "format_response",
            END: END,
        },
    )
    workflow.add_edge("call_tool", "format_response")
    workflow.add_edge("format_response", END)

    return workflow.compile()
