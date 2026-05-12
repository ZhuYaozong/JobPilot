"""LangGraph workflow for the assistant.

Slice 4 nodes: ``decide`` → optional self-loop on a single ``decide`` repair →
optional ``call_tool`` → ``format_response`` → ``maybe_summarize``.

The graph state intentionally carries only serialisable fields (ints, strings,
dicts, lists). The AsyncSession and current User are passed to nodes via
closures built at compile time, so the state can later be persisted or
streamed without extra machinery.

Slice 4 promotes the workflow from slice 3 in three ways:

- ``conversation_history`` and ``existing_summary`` are pre-loaded by the
  caller and threaded into both the decide and format_response prompts so the
  agent sees prior turns.
- A single ``decide`` repair attempt: if the first decide call returns
  unparseable or schema-mismatched output, the workflow loops back to decide
  with the previous raw output + error description in the prompt. If the
  retry also fails, we bail out with ``decide_repair_failed`` and the caller
  marks the AgentRun failed.
- A ``maybe_summarize`` node at the tail: when the conversation has grown
  past a threshold, it asks the LLM for a fresh memory summary and stashes it
  in state for the caller to persist. Failures here are non-blocking — the
  user still gets the assistant reply; we just leave the previous summary in
  place and surface the failure via a soft signal.
"""

from typing import Any, Literal, TypedDict

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


# Trigger a memory summary write when the conversation has at least this
# many persisted messages (including the user/assistant pair we are about
# to add). Slice 4 keeps the same threshold as documented in the slice plan;
# the maybe_summarize node enforces it.
SUMMARIZE_MESSAGE_THRESHOLD = 20


class AgentState(TypedDict, total=False):
    # Inputs (populated by the caller before invoke).
    user_id: int
    conversation_id: int
    user_message_id: int
    user_text: str
    agent_run_id: int
    # Pre-loaded multi-turn context.
    conversation_history: list[dict[str, str]]
    existing_summary: str | None
    # Total persisted message count *before* the current user message — used
    # by maybe_summarize to decide whether to write a summary this turn.
    message_count_before_user: int

    # `decide` node output / repair scratchpad.
    action: Literal["call_tool", "respond_directly"]
    tool_name: str | None
    tool_args: dict[str, Any] | None
    direct_text: str | None
    decide_repair_attempts: int
    decide_last_raw_output: str | None
    decide_last_error: str | None

    # `call_tool` node output.
    tool_result: dict[str, Any] | None

    # `format_response` node output.
    final_text: str

    # `maybe_summarize` node output. ``new_summary`` is the text the caller
    # should persist into memory_summaries; ``summary_error`` is set on
    # non-blocking failure (e.g. LLM down at summarise time).
    new_summary: str | None
    summary_error: str | None

    # Hard failure signalling — populated only when decide produces
    # unrecoverable garbage even after one repair attempt. assistant_service
    # treats this as a system-level failure.
    decide_error_class: str | None
    decide_error_detail: str | None


class _DecideEnvelope(BaseModel):
    """Strict shape we ask the decide LLM to emit. Pydantic catches drift."""

    action: Literal["call_tool", "respond_directly"]
    tool: str | None = None
    args: dict[str, Any] | None = None
    text: str | None = None


class WorkflowDecideError(Exception):
    """Raised when the workflow fails in a way that should fail the AgentRun.

    Currently only fired for LLM config / network errors. JSON / Pydantic
    failures take the in-state ``decide_error_class`` path so the repair loop
    can run first.
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
):
    """Compile a fresh LangGraph workflow for a single request.

    The graph is bound to ``db``, ``current_user``, and ``agent_run_id`` via
    closures, so a workflow instance is single-use.
    """

    client = llm_client or LLMClient()

    async def decide_node(state: AgentState) -> dict[str, Any]:
        attempts = int(state.get("decide_repair_attempts") or 0)
        history = state.get("conversation_history") or []
        existing_summary = state.get("existing_summary")

        if attempts == 0:
            prompt = build_decide_prompt(
                state["user_text"], history=history, existing_summary=existing_summary,
            )
        else:
            prompt = build_decide_repair_prompt(
                state["user_text"],
                history=history,
                existing_summary=existing_summary,
                previous_raw_output=state.get("decide_last_raw_output") or "",
                error_description=state.get("decide_last_error") or "unknown error",
            )

        try:
            raw = await client.generate_text(prompt)
        except LLMConfigError as exc:
            raise WorkflowDecideError("llm_config_missing", str(exc)) from exc
        except LLMClientError as exc:
            raise WorkflowDecideError("llm_unavailable", str(exc)) from exc

        # Parse + validate. On failure: if we still have a repair budget,
        # stash the error and stay on the decide node for one more shot;
        # otherwise mark the run failed via decide_error_class.
        try:
            parsed = load_llm_json(raw)
        except ValueError as exc:
            error = f"output is not valid JSON: {exc}"
            return _decide_failure(attempts, raw, error, "decide_output_not_json")

        try:
            envelope = _DecideEnvelope.model_validate(parsed)
        except ValidationError as exc:
            error = f"JSON did not match required schema: {exc}"
            return _decide_failure(attempts, raw, error, "decide_output_schema_mismatch")

        if envelope.action == "call_tool":
            if envelope.tool not in TOOL_REGISTRY:
                error = f"tool {envelope.tool!r} is not registered"
                return _decide_failure(attempts, raw, error, "decide_chose_unknown_tool")
            return {
                "action": "call_tool",
                "tool_name": envelope.tool,
                "tool_args": envelope.args or {},
                # Clear any prior repair signals so downstream nodes see a
                # clean decision.
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
            # Slice 4 still has no tool-arg repair (the decide repair only
            # covers decide's own output). Surface the failure as a soft
            # business error so format_response can apologise.
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
        history = state.get("conversation_history") or []

        if state.get("action") == "respond_directly":
            return {"final_text": (state.get("direct_text") or "").strip()}

        tool_name = state.get("tool_name") or ""
        tool_result = state.get("tool_result") or {}
        prompt = build_format_response_prompt(
            user_text=state["user_text"],
            tool_name=tool_name,
            tool_result=tool_result,
            history=history,
        )
        try:
            text = await client.generate_text(prompt)
        except (LLMConfigError, LLMClientError) as exc:
            raise WorkflowDecideError("format_response_llm_failed", str(exc)) from exc
        return {"final_text": text.strip()}

    async def maybe_summarize_node(state: AgentState) -> dict[str, Any]:
        # The user message has been persisted but the assistant message will
        # be written by the caller after the graph returns. We pre-count both
        # so the threshold reflects post-turn state.
        message_count_after_turn = int(state.get("message_count_before_user") or 0) + 2
        if message_count_after_turn < SUMMARIZE_MESSAGE_THRESHOLD:
            return {}

        history = list(state.get("conversation_history") or [])
        # Include this turn's user and tentative assistant message so the
        # summary covers them too.
        history.append({"role": "user", "content": state["user_text"]})
        history.append({"role": "assistant", "content": state.get("final_text") or ""})

        prompt = build_summarize_prompt(history)
        try:
            text = await client.generate_text(prompt)
        except (LLMConfigError, LLMClientError) as exc:
            # Non-blocking: leave the previous summary in place and surface
            # the failure so the caller can record it on the agent_run.
            return {"summary_error": f"summary_llm_failed: {exc}"}

        new_summary = text.strip()
        if not new_summary:
            return {"summary_error": "summary_llm_returned_empty"}
        return {"new_summary": new_summary}

    def route_after_decide(state: AgentState) -> str:
        if state.get("decide_error_class"):
            # Repair attempts exhausted — bail out.
            return END
        if state.get("decide_last_error"):
            # We have a repair signal but no hard error_class yet → loop back.
            return "decide"
        if state.get("action") == "call_tool":
            return "call_tool"
        return "format_response"

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
    workflow.add_edge("call_tool", "format_response")
    workflow.add_edge("format_response", "maybe_summarize")
    workflow.add_edge("maybe_summarize", END)

    return workflow.compile()


def _decide_failure(
    previous_attempts: int,
    raw_output: str,
    error: str,
    hard_error_class: str,
) -> dict[str, Any]:
    """Centralise the decide-node failure bookkeeping.

    If we still have a repair budget left, stash the error so the next decide
    invocation re-prompts with it; otherwise upgrade to the hard
    decide_error_class which bails out of the graph.
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
