"""单轮 Assistant 对话的协调服务。

这个模块把 HTTP 请求和 LangGraph workflow 串起来，职责包括：
1. 解析或创建当前用户自己的 conversation。
2. 写入用户消息，并分配正确的 ``sequence_no``。
3. 预加载最近对话历史和已有 memory_summary，让 workflow 的 decide / format_response
   节点具备多轮上下文。
4. 创建 ``AgentRun(status=running)``，并把 id 传入 workflow，使 ToolCallLog 能正确归属。
5. 执行 LangGraph workflow。
6. 成功时写入助手消息，标记 AgentRun succeeded，更新 conversation.last_run_at；
   如果 workflow 产出新摘要，则 upsert memory_summaries。
7. 系统级失败时只标记 AgentRun failed，不写助手消息，并把错误通过响应暴露给调用方。
8. 重新查询必要行，组装带完整工具调用轨迹的响应 DTO。
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
from app.models.knowledge_base import KnowledgeBase
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


# decide / format_response prompt 中保留的最近消息数。窗口越大越耗 token；
# 更早的历史由 memory_summary 覆盖。
HISTORY_WINDOW = 8


async def run_assistant_turn(
    db: AsyncSession,
    current_user: User,
    payload: AssistantRunRequest,
    llm_client: LLMClient | None = None,
) -> AssistantRunResponse:
    # 提前保存 user id。workflow 中的工具适配器可能在请求中途 rollback session，
    # 导致所有挂在 session 上的 ORM 实例过期；之后同步读取 current_user.id 可能触发
    # async greenlet 外的 lazy load，抛 MissingGreenlet。
    current_user_id = current_user.id

    conversation = await _get_or_create_conversation(
        db, current_user, payload.conversation_id,
        first_user_text=payload.content,
    )
    # 数据库里只保存用户原文，不保存 context hint，保证 UI 展示的就是用户输入。
    user_message = await _append_user_message(db, conversation, current_user, payload.content)

    # workflow 看到的是“上下文提示 + 用户问题”。如果右侧选择器已经选中简历/岗位/投递，
    # Agent 就能在用户说“这个岗位”时直接用 id，不必再调用 list_user_* 猜测。
    context_hint, selected_knowledge_base_id = await _build_context_hint(
        db, current_user.id, payload.context,
    )
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

    # 主键也提前快照，理由同 current_user_id：后续 rollback 后不再依赖 ORM 实例属性。
    conversation_id = conversation.id
    user_message_id = user_message.id
    agent_run_id = agent_run.id

    # 预加载多轮上下文。当前用户消息会作为 user_text 单独进 prompt，所以历史窗口里要排除它。
    # message_count_before_user 用来判断本轮结束后是否达到摘要阈值。
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
        "selected_knowledge_base_id": selected_knowledge_base_id,
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

    # 重新进入干净事务后再取一次对象。db.get 会先查 identity map，
    # 但对已过期的属性仍会发起 SELECT，因此这里拿到的对象状态是可靠加载过的。
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

    # 如果 maybe_summarize 产出了新摘要，这里立即 upsert。
    # 截止消息推进到本轮助手回复，下一轮加载最近历史时就会从摘要之后开始。
    new_summary = final_state.get("new_summary")
    if new_summary:
        await _upsert_memory_summary(
            db,
            conversation_id=conversation_id,
            user_id=current_user_id,
            summary_text=new_summary,
            based_on_until_message_id=assistant_message_id,
        )

    # 为可观测性推导本轮意图。ReAct 循环最后的 ``action`` 通常是
    # respond_directly，但中途可能已经调用过多个工具；因此从
    # tool_call_history 末尾向前找最后一个非发现类工具（list_user_* 只是查询）。
    # 如果本轮完全没有工具调用，则回落为 "chat"。
    intent = (
        "mock_interview"
        if _is_mock_interview_mode(payload.context)
        else _derive_intent(final_state.get("tool_call_history") or [])
    )
    finished_at = datetime.now(timezone.utc)
    agent_run.status = "succeeded"
    agent_run.intent = intent
    agent_run.finished_at = finished_at
    # 摘要失败不阻断本轮对话，因此只记录到 error_detail（不写 error_class）。
    # 这样 agent_run 仍然算成功，但排查 trace 时能看到这个软失败。
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
    """``run_assistant_turn`` 的流式版本。

    这里会产出一串事件，SSE endpoint 会把它们序列化成
    ``event: <type>\\ndata: <json>\\n\\n`` 帧。事件形态如下：

    - ``started``：用户消息入库后立即发送一次。前端用它把 optimistic
      占位消息替换成服务端真实消息，并记录可能刚创建的 ``conversation_id``。
    - ``phase``：工作流节点切换高层阶段时发送，例如 deciding / formatting /
      summarizing，用于驱动聊天输入中的“思考中”状态文案。
    - ``tool_call_started`` / ``tool_call_completed``：每次工具调用前后成对发送，
      让前端能展示“正在查询岗位……”这类实时轨迹。
    - ``message``：成功时只发送一次，携带最终助手消息和 agent_run 摘要；
      DTO 结构与旧版 /run 响应保持一致。
    - ``error``：失败时只发送一次，携带 error_class、detail 和 agent_run 摘要，
      前端可据此展示“重试”入口。
    - ``done``：永远作为最后一个事件，提示消费端可以关闭连接。

    实现上用 ``asyncio.create_task`` 并发驱动工作流，再用 ``asyncio.Queue``
    把工作流节点内部的 ``emit_event`` 回调桥接到当前 generator。这样事件一发生
    就能被 yield 出去，而不是等整轮对话全部结束后再一次性返回。
    """
    current_user_id = current_user.id

    conversation = await _get_or_create_conversation(
        db, current_user, payload.conversation_id,
        first_user_text=payload.content,
    )
    user_message = await _append_user_message(
        db, conversation, current_user, payload.content,
    )

    context_hint, selected_knowledge_base_id = await _build_context_hint(
        db, current_user.id, payload.context,
    )
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

    # 告诉前端用户消息已经在服务端落库。这里通过 _fetch_message_row 重新查询，
    # 拿到与旧版 /run endpoint 一致的扁平行结构，保持 /run 与 /run-stream 契约一致。
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
        "selected_knowledge_base_id": selected_knowledge_base_id,
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

    # 转发 workflow 运行中的事件。这里让 ``queue.get()`` 和完成信号竞速：
    # workflow 一结束就跳出循环，再把结束前刚入队的事件 drain 掉。
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
        # 等待 workflow_task 本身收尾；按信号它应该已经完成，但 await 一次可以清掉挂起异常。
        await workflow_task

    # ----- 收尾 --------------------------------------------------------------

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

    # 成功路径逐步对齐 run_assistant_turn，确保两个 endpoint 最终留下完全一致的数据库状态。
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

    intent = (
        "mock_interview"
        if _is_mock_interview_mode(payload.context)
        else _derive_intent(final_state.get("tool_call_history") or [])
    )
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
    """根据本轮工具调用推导 ``agent_runs.intent``。

    动作工具（analyze_match、generate_cover_letter 等）优先于发现类工具（list_user_*）。
    如果本轮只调用了列表工具，就记录最后一个，方便 eval / metrics 仍能看到用户在查什么。
    """
    if not tool_call_history:
        return "chat"
    for entry in reversed(tool_call_history):
        tool_name = entry.get("tool")
        if tool_name and not tool_name.startswith("list_user_"):
            return tool_name
    return tool_call_history[-1].get("tool") or "chat"


def _is_mock_interview_mode(context: ContextSelection | None) -> bool:
    return context is not None and context.assistant_mode == "mock_interview"


async def _build_context_hint(
    db: AsyncSession,
    user_id: int,
    context: ContextSelection | None,
) -> tuple[str | None, int | None]:
    """把 UI 侧选择器里的 id 解析成 prompt 可读的上下文提示。

    这个提示刻意短而有标签，LLM 会看到类似：

        [当前上下文]
        - 简历:Backend Resume v2 (#7)
        - 岗位:腾讯 · 后端工程师 (#12)
        - 投递记录:#3

    如果某个 id 已被删除或不属于当前用户，就静默跳过。右侧选择器可能短暂指向刚删除的行，
    这种 UI 状态不应该让整轮 Assistant 请求失败。
    """
    if context is None:
        return None, None

    lines: list[str] = []
    selected_knowledge_base_id: int | None = None

    if context.assistant_mode == "mock_interview":
        lines.append(
            "- 模式:模拟面试; "
            "如果缺少简历或岗位,先请用户选择; "
            "如果已选简历和岗位,围绕它们进行交互式面试,每轮只问一个问题",
        )

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
        # 投递记录暂时没有友好标题；id 已足够让 LLM 需要时调用 list_user_applications 补详情。
        lines.append(f"- 投递记录:#{context.application_record_id}")

    if context.knowledge_base_id is not None:
        row = (
            await db.execute(
                select(KnowledgeBase.id, KnowledgeBase.name).where(
                    KnowledgeBase.id == context.knowledge_base_id,
                    KnowledgeBase.user_id == user_id,
                ),
            )
        ).one_or_none()
        if row is not None:
            selected_knowledge_base_id = row.id
            lines.append(
                f"- 知识库:{row.name} (#{row.id}); "
                "如需检索资料,调用 search_knowledge 时必须使用此 knowledge_base_id",
            )

    if not lines:
        return None, selected_knowledge_base_id
    return "[当前上下文]\n" + "\n".join(lines), selected_knowledge_base_id


_MAX_TITLE_CHARS = 28


def _derive_title(first_user_text: str) -> str:
    """从第一条用户消息派生会话标题。

    策略很简单：折叠空白后截到 ``_MAX_TITLE_CHARS``，超长时加省略号。理论上 content
    有 min_length=1，不会是空；这里仍保留时间占位标题作为防御。
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
    """读取会话摘要。

    有摘要时返回 ``(summary_text, based_on_until_message_id)``；没有摘要时返回
    ``(None, None)``。
    """
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
    """为 decide / format_response prompt 读取最近消息，返回顺序为从旧到新。

    - ``exclude_message_id`` 是刚写入的当前用户消息，prompt 会通过 ``user_text`` 单独接收，
      这里排除它以避免重复。
    - ``after_message_id`` 是已有摘要覆盖到的消息 id；小于等于该 id 的内容已在摘要里，
      不再放入最近窗口。
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
    rows.reverse()  # prompt 里按自然阅读顺序呈现：旧消息在前，新消息在后。
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
    # 请求中途失败时先 rollback，清掉 workflow 可能留下的半事务状态。
    # rollback 后 ORM 实例会过期，所以后面只按 id 重新读取，不再碰旧实例属性。
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
    # 这里刻意重新 select 每一行，并且只 select 具体列，得到普通 tuple 后手工构造 DTO。
    # 工具适配器可能在请求中途 rollback，使 session 上的 ORM 实例全部过期；如果直接让
    # Pydantic from_attributes 同步 getattr，可能触发 async greenlet 外的 lazy-load，
    # 最终抛 MissingGreenlet。列元组没有这个问题。
    # AsyncSession.expire_all 是同步方法（无 I/O），不要 await。
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
