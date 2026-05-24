from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUserDep, DbSession, ListLimit, ListOffset
from app.models.agent_run import AgentRun
from app.models.conversation import Conversation
from app.models.memory_summary import MemorySummary
from app.models.message import Message
from app.models.tool_call_log import ToolCallLog
from app.schemas.agent_run import AgentRunWithToolCallsRead, ToolCallLogRead
from app.schemas.conversation import (
    ConversationListItem,
    ConversationRead,
    ConversationUpdate,
)
from app.schemas.message import MessageRead

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationListItem])
async def list_conversations(
    db: DbSession,
    current_user: CurrentUserDep,
    limit: ListLimit = 20,
    offset: ListOffset = 0,
) -> list[Conversation]:
    # 优先按 last_run_at 倒序，让刚聊过的会话浮到顶部；新建但还没完成 AgentRun 的会话
    # 没有 last_run_at，则退回 updated_at。
    statement = (
        select(Conversation)
        .where(Conversation.user_id == current_user.id)
        .order_by(
            Conversation.last_run_at.desc().nullslast(),
            Conversation.updated_at.desc(),
            Conversation.id.desc(),
        )
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(statement)
    return list(result.scalars().all())


@router.get("/{conversation_id}/messages", response_model=list[MessageRead])
async def list_messages(
    conversation_id: int,
    db: DbSession,
    current_user: CurrentUserDep,
) -> list[Message]:
    await _require_owned_conversation(db, conversation_id, current_user.id)

    statement = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.sequence_no.asc(), Message.id.asc())
    )
    result = await db.execute(statement)
    return list(result.scalars().all())


@router.get(
    "/{conversation_id}/agent-runs",
    response_model=list[AgentRunWithToolCallsRead],
)
async def list_conversation_agent_runs(
    conversation_id: int,
    db: DbSession,
    current_user: CurrentUserDep,
) -> list[AgentRunWithToolCallsRead]:
    """列出某会话的所有 AgentRun 以及每次运行内的工具调用(任务 4 Agent 可观测)。

    用户作用域:只返回 current_user 自己的 AgentRun。
    返回顺序:AgentRun 按 started_at 升序;每个 AgentRun 内部 tool_calls 也按 started_at 升序。
    会话不存在或跨用户访问 → 404。
    """
    await _require_owned_conversation(db, conversation_id, current_user.id)

    # 先一条 select 拿到该会话的所有 AgentRun(按时间序),
    # 再一条 select 拿到这些 AgentRun 关联的所有 ToolCallLog;
    # 用 dict 按 agent_run_id 分组,避免 N+1 子查询。
    agent_runs_result = await db.execute(
        select(AgentRun)
        .where(
            AgentRun.conversation_id == conversation_id,
            AgentRun.user_id == current_user.id,
        )
        .order_by(AgentRun.started_at.asc(), AgentRun.id.asc()),
    )
    agent_runs = list(agent_runs_result.scalars().all())
    if not agent_runs:
        return []

    agent_run_ids = [run.id for run in agent_runs]
    tool_calls_result = await db.execute(
        select(ToolCallLog)
        .where(ToolCallLog.agent_run_id.in_(agent_run_ids))
        .order_by(ToolCallLog.started_at.asc(), ToolCallLog.id.asc()),
    )
    tool_calls_by_run: dict[int, list[ToolCallLogRead]] = {}
    for call in tool_calls_result.scalars().all():
        tool_calls_by_run.setdefault(call.agent_run_id, []).append(
            ToolCallLogRead.model_validate(call),
        )

    return [
        AgentRunWithToolCallsRead.model_validate(
            {
                "id": run.id,
                "conversation_id": run.conversation_id,
                "trigger_message_id": run.trigger_message_id,
                "status": run.status,
                "intent": run.intent,
                "error_class": run.error_class,
                "error_detail": run.error_detail,
                "token_usage": run.token_usage,
                "started_at": run.started_at,
                "finished_at": run.finished_at,
                "tool_calls": tool_calls_by_run.get(run.id, []),
            },
        )
        for run in agent_runs
    ]


@router.patch("/{conversation_id}", response_model=ConversationRead)
async def update_conversation(
    conversation_id: int,
    payload: ConversationUpdate,
    db: DbSession,
    current_user: CurrentUserDep,
) -> Conversation:
    """重命名会话，或更新会话状态。

    当前 UI 只暴露 title；schema 预留 ``status``，后续可接归档、置顶等能力。
    """
    conversation = await _require_owned_conversation(
        db, conversation_id, current_user.id,
    )

    if payload.title is not None:
        trimmed = payload.title.strip()
        if not trimmed:
            raise HTTPException(status_code=400, detail="title cannot be empty")
        if len(trimmed) > 255:
            raise HTTPException(status_code=400, detail="title too long")
        conversation.title = trimmed

    if payload.status is not None:
        conversation.status = payload.status

    await db.commit()
    await db.refresh(conversation)
    return conversation


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: int,
    db: DbSession,
    current_user: CurrentUserDep,
) -> Response:
    """硬删除一个会话及其拥有的所有行。

    messages / agent_runs / memory_summaries 上的外键没有 ``ON DELETE CASCADE``，
    因此这里手工按依赖顺序拆图：

        tool_call_logs → agent_runs → memory_summaries / messages → conversation

    所有删除在一个事务里完成，即使用户中途关页面，也不会留下半删除状态。
    """
    await _require_owned_conversation(db, conversation_id, current_user.id)

    # tool_call_logs 依赖 agent_runs。先查出 agent_run ids，后面就能用一条 DELETE 批量删日志。
    agent_run_ids = (
        await db.execute(
            select(AgentRun.id).where(AgentRun.conversation_id == conversation_id),
        )
    ).scalars().all()

    if agent_run_ids:
        await db.execute(
            update(Message)
            .where(Message.conversation_id == conversation_id)
            .where(Message.agent_run_id.in_(agent_run_ids))
            .values(agent_run_id=None),
        )
        await db.execute(
            update(AgentRun)
            .where(AgentRun.id.in_(agent_run_ids))
            .values(trigger_message_id=None),
        )
        await db.execute(
            delete(ToolCallLog).where(ToolCallLog.agent_run_id.in_(agent_run_ids)),
        )

    await db.execute(
        delete(MemorySummary).where(MemorySummary.conversation_id == conversation_id),
    )
    await db.execute(
        delete(AgentRun).where(AgentRun.conversation_id == conversation_id),
    )
    await db.execute(
        delete(Message).where(Message.conversation_id == conversation_id),
    )
    await db.execute(
        delete(Conversation).where(Conversation.id == conversation_id),
    )
    await db.commit()
    return Response(status_code=204)


async def _require_owned_conversation(
    db: AsyncSession,
    conversation_id: int,
    user_id: int,
) -> Conversation:
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user_id,
        ),
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation
