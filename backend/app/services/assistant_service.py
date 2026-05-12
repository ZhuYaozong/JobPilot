"""Coordinator for one assistant turn.

Responsibilities:
1. Resolve (or create) the conversation, scoped to the current user.
2. Persist the inbound user message with the right ``sequence_no``.
3. Pre-load conversation history + any existing memory_summary so the
   workflow's decide / format_response nodes see multi-turn context.
4. Open an ``AgentRun`` (status=running) and pass its id into the workflow so
   ``ToolCallLog`` rows link back correctly.
5. Run the LangGraph workflow.
6. On success: persist the assistant message, mark the AgentRun succeeded,
   bump ``conversation.last_run_at``; upsert ``memory_summaries`` if the
   workflow produced a new summary.
7. On system-level failure: mark the AgentRun failed; do **not** write an
   assistant message; surface the error to the caller via the response.
8. Build the response DTO with full tool-call traces for the UI.
"""

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tool_adapter import ToolSystemError
from app.agent.workflow import WorkflowDecideError, build_workflow
from app.llm.client import LLMClient
from app.models.agent_run import AgentRun
from app.models.conversation import Conversation
from app.models.memory_summary import MemorySummary
from app.models.message import Message
from app.models.tool_call_log import ToolCallLog
from app.models.user import User
from app.models.job_posting import JobPosting
from app.models.resume import Resume
from app.schemas.assistant import (
    AgentRunSummary,
    AssistantRunRequest,
    AssistantRunResponse,
    ContextSelection,
    ToolCallTrace,
)
from app.schemas.message import MessageRead


# How many recent turns (post-summary) to put in the decide / format_response
# prompts. Larger windows cost tokens; the summary covers earlier history.
HISTORY_WINDOW = 8


async def run_assistant_turn(
    db: AsyncSession,
    current_user: User,
    payload: AssistantRunRequest,
    llm_client: LLMClient | None = None,
) -> AssistantRunResponse:
    # Snapshot the user id up-front. After the workflow's tool adapter calls
    # ``ctx.db.rollback()`` mid-request, every ORM instance attached to this
    # session is expired — a later sync ``current_user.id`` access can trigger
    # a lazy load outside an async greenlet and surface as MissingGreenlet.
    current_user_id = current_user.id

    conversation = await _get_or_create_conversation(
        db, current_user, payload.conversation_id,
        first_user_text=payload.content,
    )
    # Store the user's clean text in the message row (no hint prefix) so the
    # UI displays exactly what the user typed.
    user_message = await _append_user_message(db, conversation, current_user, payload.content)

    # Build the workflow-facing user_text. If the right-side selector pre-
    # picked a resume/job/application, prepend a labelled hint so the agent
    # can short-circuit list_user_* tools when the user said "这个岗位".
    context_hint = await _build_context_hint(db, current_user.id, payload.context)
    workflow_user_text = (
        f"{context_hint}\n\n[用户问题]\n{payload.content}"
        if context_hint
        else payload.content
    )

    agent_run = AgentRun(
        user_id=current_user_id,
        conversation_id=conversation.id,
        trigger_message_id=user_message.id,
        status="running",
    )
    db.add(agent_run)
    await db.commit()
    await db.refresh(agent_run)

    # Capture every primary key for the same reason as current_user_id above.
    conversation_id = conversation.id
    user_message_id = user_message.id
    agent_run_id = agent_run.id

    # Pre-load multi-turn context. The current user_message is excluded from
    # the history window because the prompts pass it separately as
    # ``user_text``. ``message_count_before_user`` lets maybe_summarize decide
    # whether the conversation has crossed the summarisation threshold.
    existing_summary_text, summary_cutoff_message_id = await _load_existing_summary(
        db, conversation_id,
    )
    history = await _load_recent_history(
        db,
        conversation_id=conversation_id,
        exclude_message_id=user_message_id,
        after_message_id=summary_cutoff_message_id,
        limit=HISTORY_WINDOW,
    )
    message_count_before_user = await _count_messages(db, conversation_id) - 1

    workflow = build_workflow(
        db=db,
        current_user=current_user,
        agent_run_id=agent_run_id,
        llm_client=llm_client,
    )

    initial_state: dict[str, Any] = {
        "user_id": current_user.id,
        "conversation_id": conversation_id,
        "user_message_id": user_message_id,
        "user_text": workflow_user_text,
        "agent_run_id": agent_run_id,
        "conversation_history": history,
        "existing_summary": existing_summary_text,
        "message_count_before_user": message_count_before_user,
        "decide_repair_attempts": 0,
        "iteration_count": 0,
        "tool_call_history": [],
    }

    try:
        final_state = await workflow.ainvoke(initial_state)
    except (WorkflowDecideError, ToolSystemError) as exc:
        return await _finalize_failed_run(
            db,
            agent_run_id=agent_run_id,
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            error_class=exc.error_class if hasattr(exc, "error_class") else "workflow_failure",
            error_detail=str(exc),
        )
    except Exception as exc:  # noqa: BLE001 — last-ditch safety net
        return await _finalize_failed_run(
            db,
            agent_run_id=agent_run_id,
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            error_class="unexpected_workflow_error",
            error_detail=f"{type(exc).__name__}: {exc}",
        )

    decide_error_class = final_state.get("decide_error_class")
    if decide_error_class:
        return await _finalize_failed_run(
            db,
            agent_run_id=agent_run_id,
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            error_class=decide_error_class,
            error_detail=final_state.get("decide_error_detail") or "",
        )

    final_text = (final_state.get("final_text") or "").strip()
    if not final_text:
        return await _finalize_failed_run(
            db,
            agent_run_id=agent_run_id,
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            error_class="empty_assistant_response",
            error_detail="workflow returned no text",
        )

    # Re-fetch into a fresh transaction. db.get checks the identity map first
    # but issues a SELECT for any expired attributes, so the returned objects
    # are reliably loaded.
    db.expire_all()
    conversation = await db.get(Conversation, conversation_id)
    agent_run = await db.get(AgentRun, agent_run_id)
    assert conversation is not None and agent_run is not None

    assistant_message_id = await _append_assistant_message(
        db,
        conversation_id=conversation_id,
        user_id=current_user_id,
        content=final_text,
        agent_run_id=agent_run_id,
    )

    # If maybe_summarize produced a new summary, upsert it now. The cutoff
    # advances to this turn's assistant message so the next call's history
    # window starts after it.
    new_summary = final_state.get("new_summary")
    if new_summary:
        await _upsert_memory_summary(
            db,
            conversation_id=conversation_id,
            user_id=current_user_id,
            summary_text=new_summary,
            based_on_until_message_id=assistant_message_id,
        )

    # Derive intent for traceability. In the ReAct loop the final ``action``
    # is usually respond_directly, but the agent may have called several tools
    # along the way. Walk tool_call_history from the end and pick the last
    # non-discovery tool (list_user_* are pure lookups). Falls back to "chat"
    # when no tool was called at all.
    intent = _derive_intent(final_state.get("tool_call_history") or [])
    finished_at = datetime.now(timezone.utc)
    agent_run.status = "succeeded"
    agent_run.intent = intent
    agent_run.finished_at = finished_at
    # A non-blocking summarize failure is recorded as error_detail (not
    # error_class) so the run still counts as succeeded but operators can see
    # the soft failure in the trace.
    summary_error = final_state.get("summary_error")
    if summary_error:
        agent_run.error_detail = f"non_blocking_summary_failure: {summary_error}"
    conversation.last_run_at = finished_at
    await db.commit()

    return await _build_response(
        db,
        conversation_id=conversation_id,
        user_message_id=user_message_id,
        assistant_message_id=assistant_message_id,
        agent_run_id=agent_run_id,
    )


async def run_assistant_turn_stream(
    db: AsyncSession,
    current_user: User,
    payload: AssistantRunRequest,
    llm_client: LLMClient | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Streaming counterpart to :func:`run_assistant_turn`.

    Yields a sequence of events that the SSE endpoint serialises as
    ``event: <type>\\ndata: <json>\\n\\n`` frames. The shape:

    - ``started`` — once, immediately after the user message is persisted.
      Lets the UI replace its optimistic placeholder with the server-side
      message and remember the (possibly new) ``conversation_id``.
    - ``phase`` — every time a node changes the high-level activity
      ("deciding" / "formatting" / "summarizing"). Drives the chat's typing
      indicator copy.
    - ``tool_call_started`` / ``tool_call_completed`` — bracket each tool
      invocation so the UI can show a live trace of "正在查询岗位……" etc.
    - ``message`` — exactly once on success, carries the final assistant
      message + agent_run summary (same DTOs as the legacy /run response).
    - ``error`` — exactly once on failure, carries error_class + detail and
      the agent_run summary so the UI can offer "重试".
    - ``done`` — always last; signals the consumer to close the connection.

    Implementation note: the workflow is driven concurrently via
    ``asyncio.create_task``; an ``asyncio.Queue`` bridges the workflow's
    in-node ``emit_event`` callbacks to this generator so each event can be
    yielded the instant it happens, not deferred until the whole turn
    completes.
    """
    current_user_id = current_user.id

    conversation = await _get_or_create_conversation(
        db, current_user, payload.conversation_id,
        first_user_text=payload.content,
    )
    user_message = await _append_user_message(
        db, conversation, current_user, payload.content,
    )

    context_hint = await _build_context_hint(db, current_user.id, payload.context)
    workflow_user_text = (
        f"{context_hint}\n\n[用户问题]\n{payload.content}"
        if context_hint
        else payload.content
    )

    agent_run = AgentRun(
        user_id=current_user_id,
        conversation_id=conversation.id,
        trigger_message_id=user_message.id,
        status="running",
    )
    db.add(agent_run)
    await db.commit()
    await db.refresh(agent_run)

    conversation_id = conversation.id
    user_message_id = user_message.id
    agent_run_id = agent_run.id

    # Tell the UI the message has been persisted server-side. We refetch via
    # _fetch_message_row to get the same flat row the legacy endpoint returns
    # — keeps the contract aligned between /run and /run-stream.
    user_message_dto = await _fetch_message_row(db, user_message_id)
    yield {
        "event": "started",
        "data": {
            "conversation_id": conversation_id,
            "user_message": user_message_dto.model_dump(mode="json"),
        },
    }

    existing_summary_text, summary_cutoff_message_id = await _load_existing_summary(
        db, conversation_id,
    )
    history = await _load_recent_history(
        db,
        conversation_id=conversation_id,
        exclude_message_id=user_message_id,
        after_message_id=summary_cutoff_message_id,
        limit=HISTORY_WINDOW,
    )
    message_count_before_user = await _count_messages(db, conversation_id) - 1

    event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

    async def emit_event(event_type: str, data: dict[str, Any]) -> None:
        await event_queue.put({"event": event_type, "data": data})

    workflow = build_workflow(
        db=db,
        current_user=current_user,
        agent_run_id=agent_run_id,
        llm_client=llm_client,
        emit_event=emit_event,
    )

    initial_state: dict[str, Any] = {
        "user_id": current_user.id,
        "conversation_id": conversation_id,
        "user_message_id": user_message_id,
        "user_text": workflow_user_text,
        "agent_run_id": agent_run_id,
        "conversation_history": history,
        "existing_summary": existing_summary_text,
        "message_count_before_user": message_count_before_user,
        "decide_repair_attempts": 0,
        "iteration_count": 0,
        "tool_call_history": [],
    }

    workflow_exception: Exception | None = None
    workflow_final_state: dict[str, Any] | None = None
    workflow_done_signal = asyncio.Event()

    async def _drive_workflow() -> None:
        nonlocal workflow_exception, workflow_final_state
        try:
            workflow_final_state = await workflow.ainvoke(initial_state)
        except Exception as exc:  # noqa: BLE001 — surfaced via error event below
            workflow_exception = exc
        finally:
            workflow_done_signal.set()

    workflow_task = asyncio.create_task(_drive_workflow())

    # Relay in-flight events. We race ``queue.get()`` against
    # ``workflow_done_signal`` so the loop exits as soon as the workflow
    # finishes, then drain any events that arrived just before completion.
    try:
        while True:
            get_task = asyncio.create_task(event_queue.get())
            done_task = asyncio.create_task(workflow_done_signal.wait())
            done, _ = await asyncio.wait(
                [get_task, done_task],
                return_when=asyncio.FIRST_COMPLETED,
            )
            if get_task in done:
                done_task.cancel()
                yield get_task.result()
            else:
                get_task.cancel()
                break
        while not event_queue.empty():
            yield event_queue.get_nowait()
    finally:
        # Make sure the workflow task itself has surfaced (it should be done
        # already given we waited on the signal, but await it to clear any
        # pending exceptions).
        await workflow_task

    # ----- Finalize ---------------------------------------------------------

    if workflow_exception is not None:
        if isinstance(workflow_exception, (WorkflowDecideError, ToolSystemError)):
            error_class = getattr(
                workflow_exception, "error_class", "workflow_failure",
            )
            error_detail = str(workflow_exception)
        else:
            error_class = "unexpected_workflow_error"
            exc = workflow_exception
            error_detail = f"{type(exc).__name__}: {exc}"
        response = await _finalize_failed_run(
            db,
            agent_run_id=agent_run_id,
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            error_class=error_class,
            error_detail=error_detail,
        )
        yield {
            "event": "error",
            "data": {
                "error_class": error_class,
                "error_detail": error_detail,
                "agent_run": response.agent_run.model_dump(mode="json"),
            },
        }
        yield {"event": "done", "data": {}}
        return

    assert workflow_final_state is not None
    final_state = workflow_final_state

    decide_error_class = final_state.get("decide_error_class")
    if decide_error_class:
        response = await _finalize_failed_run(
            db,
            agent_run_id=agent_run_id,
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            error_class=decide_error_class,
            error_detail=final_state.get("decide_error_detail") or "",
        )
        yield {
            "event": "error",
            "data": {
                "error_class": decide_error_class,
                "error_detail": final_state.get("decide_error_detail") or "",
                "agent_run": response.agent_run.model_dump(mode="json"),
            },
        }
        yield {"event": "done", "data": {}}
        return

    final_text = (final_state.get("final_text") or "").strip()
    if not final_text:
        response = await _finalize_failed_run(
            db,
            agent_run_id=agent_run_id,
            conversation_id=conversation_id,
            user_message_id=user_message_id,
            error_class="empty_assistant_response",
            error_detail="workflow returned no text",
        )
        yield {
            "event": "error",
            "data": {
                "error_class": "empty_assistant_response",
                "error_detail": "workflow returned no text",
                "agent_run": response.agent_run.model_dump(mode="json"),
            },
        }
        yield {"event": "done", "data": {}}
        return

    # Success path mirrors run_assistant_turn line-for-line so both endpoints
    # leave the DB in identical state.
    db.expire_all()
    conversation_fresh = await db.get(Conversation, conversation_id)
    agent_run_fresh = await db.get(AgentRun, agent_run_id)
    assert conversation_fresh is not None and agent_run_fresh is not None

    assistant_message_id = await _append_assistant_message(
        db,
        conversation_id=conversation_id,
        user_id=current_user_id,
        content=final_text,
        agent_run_id=agent_run_id,
    )

    new_summary = final_state.get("new_summary")
    if new_summary:
        await _upsert_memory_summary(
            db,
            conversation_id=conversation_id,
            user_id=current_user_id,
            summary_text=new_summary,
            based_on_until_message_id=assistant_message_id,
        )

    intent = _derive_intent(final_state.get("tool_call_history") or [])
    finished_at = datetime.now(timezone.utc)
    agent_run_fresh.status = "succeeded"
    agent_run_fresh.intent = intent
    agent_run_fresh.finished_at = finished_at
    summary_error = final_state.get("summary_error")
    if summary_error:
        agent_run_fresh.error_detail = f"non_blocking_summary_failure: {summary_error}"
    conversation_fresh.last_run_at = finished_at
    await db.commit()

    response = await _build_response(
        db,
        conversation_id=conversation_id,
        user_message_id=user_message_id,
        assistant_message_id=assistant_message_id,
        agent_run_id=agent_run_id,
    )
    assert response.assistant_message is not None
    yield {
        "event": "message",
        "data": {
            "assistant_message": response.assistant_message.model_dump(mode="json"),
            "agent_run": response.agent_run.model_dump(mode="json"),
        },
    }
    yield {"event": "done", "data": {}}


def _derive_intent(tool_call_history: list[dict[str, Any]]) -> str:
    """Pick a short label for ``agent_runs.intent`` from the tools called.

    Action tools (analyze_match, generate_cover_letter, ...) take priority
    over discovery tools (list_user_*). If only list tools fired, we report
    the last one so eval / metrics can still see what the user looked at.
    """
    if not tool_call_history:
        return "chat"
    for entry in reversed(tool_call_history):
        tool_name = entry.get("tool")
        if tool_name and not tool_name.startswith("list_user_"):
            return tool_name
    return tool_call_history[-1].get("tool") or "chat"


async def _build_context_hint(
    db: AsyncSession,
    user_id: int,
    context: ContextSelection | None,
) -> str | None:
    """Resolve the UI-side selection to human-readable labels for the prompt.

    The hint format is intentionally short and labelled — the LLM sees:

        [当前上下文]
        - 简历:Backend Resume v2 (#7)
        - 岗位:腾讯 · 后端工程师 (#12)
        - 投递记录:#3

    Lookups silently ignore missing rows or other-user rows: we don't want a
    transient mismatch (e.g. selector still pointing at a freshly-deleted
    resume) to fail the whole assistant call.
    """
    if context is None:
        return None

    lines: list[str] = []

    if context.resume_id is not None:
        row = (
            await db.execute(
                select(Resume.id, Resume.title).where(
                    Resume.id == context.resume_id,
                    Resume.user_id == user_id,
                ),
            )
        ).one_or_none()
        if row is not None:
            lines.append(f"- 简历:{row.title} (#{row.id})")

    if context.job_posting_id is not None:
        row = (
            await db.execute(
                select(
                    JobPosting.id,
                    JobPosting.company_name,
                    JobPosting.job_title,
                ).where(
                    JobPosting.id == context.job_posting_id,
                    JobPosting.user_id == user_id,
                ),
            )
        ).one_or_none()
        if row is not None:
            lines.append(
                f"- 岗位:{row.company_name} · {row.job_title} (#{row.id})",
            )

    if context.application_record_id is not None:
        # We don't render a friendly label for applications yet; the id
        # alone is enough for the LLM to call list_user_applications if
        # it wants details.
        lines.append(f"- 投递记录:#{context.application_record_id}")

    if not lines:
        return None
    return "[当前上下文]\n" + "\n".join(lines)


_MAX_TITLE_CHARS = 28


def _derive_title(first_user_text: str) -> str:
    """Generate a conversation title from the user's first message.

    Strategy: collapse whitespace + truncate to ``_MAX_TITLE_CHARS`` chars
    (with an ellipsis if we cut anything off). Falls back to a date-stamped
    placeholder when the message is empty after trimming — should not
    happen given content is min_length=1, but defensive.
    """
    cleaned = " ".join(first_user_text.split()).strip()
    if not cleaned:
        return f"新对话 {datetime.now().strftime('%m-%d %H:%M')}"
    if len(cleaned) <= _MAX_TITLE_CHARS:
        return cleaned
    return f"{cleaned[:_MAX_TITLE_CHARS]}…"


async def _get_or_create_conversation(
    db: AsyncSession,
    current_user: User,
    conversation_id: int | None,
    first_user_text: str | None = None,
) -> Conversation:
    if conversation_id is None:
        title = _derive_title(first_user_text or "")
        conversation = Conversation(user_id=current_user.id, title=title)
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)
        return conversation

    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        ),
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


async def _next_sequence_no(db: AsyncSession, conversation_id: int) -> int:
    result = await db.execute(
        select(func.coalesce(func.max(Message.sequence_no), 0)).where(
            Message.conversation_id == conversation_id,
        ),
    )
    return int(result.scalar_one()) + 1


async def _count_messages(db: AsyncSession, conversation_id: int) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(Message)
        .where(Message.conversation_id == conversation_id),
    )
    return int(result.scalar_one())


async def _load_existing_summary(
    db: AsyncSession,
    conversation_id: int,
) -> tuple[str | None, int | None]:
    """Return ``(summary_text, based_on_until_message_id)`` if a summary
    exists for this conversation, else ``(None, None)``."""
    result = await db.execute(
        select(
            MemorySummary.summary_text,
            MemorySummary.based_on_until_message_id,
        ).where(MemorySummary.conversation_id == conversation_id),
    )
    row = result.one_or_none()
    if row is None:
        return None, None
    return row.summary_text, row.based_on_until_message_id


async def _load_recent_history(
    db: AsyncSession,
    *,
    conversation_id: int,
    exclude_message_id: int,
    after_message_id: int | None,
    limit: int,
) -> list[dict[str, str]]:
    """Return up to ``limit`` most-recent messages (oldest first) for the
    decide / format_response prompts.

    - ``exclude_message_id`` is the just-written user message; the prompts
      receive it separately as ``user_text``, so we drop it here to avoid
      duplication.
    - ``after_message_id`` is the cutoff covered by the existing memory
      summary. Anything at or before this id is already in the summary, so we
      exclude it from the recent-history window.
    """
    conditions = [
        Message.conversation_id == conversation_id,
        Message.id != exclude_message_id,
    ]
    if after_message_id is not None:
        conditions.append(Message.id > after_message_id)

    result = await db.execute(
        select(Message.role, Message.content, Message.sequence_no)
        .where(*conditions)
        .order_by(Message.sequence_no.desc())
        .limit(limit),
    )
    rows = list(result.all())
    rows.reverse()  # oldest first
    return [{"role": row.role, "content": row.content} for row in rows]


async def _upsert_memory_summary(
    db: AsyncSession,
    *,
    conversation_id: int,
    user_id: int,
    summary_text: str,
    based_on_until_message_id: int,
) -> None:
    result = await db.execute(
        select(MemorySummary).where(
            MemorySummary.conversation_id == conversation_id,
        ),
    )
    summary = result.scalar_one_or_none()
    if summary is None:
        summary = MemorySummary(
            user_id=user_id,
            conversation_id=conversation_id,
            summary_text=summary_text,
            based_on_until_message_id=based_on_until_message_id,
        )
        db.add(summary)
    else:
        summary.summary_text = summary_text
        summary.based_on_until_message_id = based_on_until_message_id
    await db.commit()


async def _append_user_message(
    db: AsyncSession,
    conversation: Conversation,
    current_user: User,
    content: str,
) -> Message:
    seq = await _next_sequence_no(db, conversation.id)
    message = Message(
        user_id=current_user.id,
        conversation_id=conversation.id,
        role="user",
        content=content,
        sequence_no=seq,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message


async def _append_assistant_message(
    db: AsyncSession,
    conversation_id: int,
    user_id: int,
    content: str,
    agent_run_id: int,
) -> int:
    seq = await _next_sequence_no(db, conversation_id)
    message = Message(
        user_id=user_id,
        conversation_id=conversation_id,
        role="assistant",
        content=content,
        sequence_no=seq,
        agent_run_id=agent_run_id,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message.id


async def _finalize_failed_run(
    db: AsyncSession,
    *,
    agent_run_id: int,
    conversation_id: int,
    user_message_id: int,
    error_class: str,
    error_detail: str,
) -> AssistantRunResponse:
    # Mid-request rollback to clear any partial state left by the workflow.
    # The session's instances will be expired afterwards; we never touch
    # them again, only re-fetch by id.
    try:
        await db.rollback()
    except Exception:  # noqa: BLE001 — best effort, mirrors tool_adapter pattern
        pass

    fresh_run = await db.get(AgentRun, agent_run_id)
    if fresh_run is not None:
        fresh_run.status = "failed"
        fresh_run.error_class = error_class
        fresh_run.error_detail = error_detail
        fresh_run.finished_at = datetime.now(timezone.utc)
        conversation_fresh = await db.get(Conversation, conversation_id)
        if conversation_fresh is not None:
            conversation_fresh.last_run_at = fresh_run.finished_at
        await db.commit()

    return await _build_response(
        db,
        conversation_id=conversation_id,
        user_message_id=user_message_id,
        assistant_message_id=None,
        agent_run_id=agent_run_id,
    )


async def _build_response(
    db: AsyncSession,
    *,
    conversation_id: int,
    user_message_id: int,
    assistant_message_id: int | None,
    agent_run_id: int,
) -> AssistantRunResponse:
    # We deliberately re-SELECT every row inside this async context with
    # explicit ``select(col1, col2, ...)`` queries (column tuples — no ORM
    # hydration), then build response objects from plain Python values. The
    # tool adapter calls ``ctx.db.rollback()`` mid-request which expires every
    # ORM instance attached to this session; subsequent sync ``getattr`` from
    # Pydantic's ``from_attributes`` could otherwise trigger a lazy-load
    # outside of an async greenlet and surface as MissingGreenlet.
    # AsyncSession.expire_all is synchronous (no I/O) — do NOT await it.
    db.expire_all()

    agent_run_row = (
        await db.execute(
            select(
                AgentRun.id,
                AgentRun.status,
                AgentRun.intent,
                AgentRun.started_at,
                AgentRun.finished_at,
                AgentRun.error_class,
                AgentRun.error_detail,
            ).where(AgentRun.id == agent_run_id),
        )
    ).one()

    user_message_row = await _fetch_message_row(db, user_message_id)
    assistant_message_row = (
        await _fetch_message_row(db, assistant_message_id)
        if assistant_message_id is not None
        else None
    )

    tool_call_rows = (
        await db.execute(
            select(
                ToolCallLog.id,
                ToolCallLog.tool_name,
                ToolCallLog.status,
                ToolCallLog.error_class,
                ToolCallLog.latency_ms,
            )
            .where(ToolCallLog.agent_run_id == agent_run_id)
            .order_by(ToolCallLog.id),
        )
    ).all()

    return AssistantRunResponse(
        conversation_id=conversation_id,
        agent_run=AgentRunSummary(
            id=agent_run_row.id,
            status=agent_run_row.status,
            intent=agent_run_row.intent,
            started_at=agent_run_row.started_at,
            finished_at=agent_run_row.finished_at,
            error_class=agent_run_row.error_class,
            error_detail=agent_run_row.error_detail,
            tool_calls=[
                ToolCallTrace(
                    id=row.id,
                    tool_name=row.tool_name,
                    status=row.status,
                    error_class=row.error_class,
                    latency_ms=row.latency_ms,
                )
                for row in tool_call_rows
            ],
        ),
        user_message=user_message_row,
        assistant_message=assistant_message_row,
    )


async def _fetch_message_row(db: AsyncSession, message_id: int) -> MessageRead:
    row = (
        await db.execute(
            select(
                Message.id,
                Message.conversation_id,
                Message.role,
                Message.content,
                Message.content_json,
                Message.agent_run_id,
                Message.sequence_no,
                Message.created_at,
            ).where(Message.id == message_id),
        )
    ).one()
    return MessageRead(
        id=row.id,
        conversation_id=row.conversation_id,
        role=row.role,
        content=row.content,
        content_json=row.content_json,
        agent_run_id=row.agent_run_id,
        sequence_no=row.sequence_no,
        created_at=row.created_at,
    )
