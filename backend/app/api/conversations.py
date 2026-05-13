from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUserDep, DbSession, ListLimit, ListOffset
from app.models.agent_run import AgentRun
from app.models.conversation import Conversation
from app.models.memory_summary import MemorySummary
from app.models.message import Message
from app.models.tool_call_log import ToolCallLog
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
    # Recent-first by last_run_at when present (so just-used conversations
    # bubble to the top), falling back to updated_at for fresh conversations
    # that have not yet completed a run.
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


@router.patch("/{conversation_id}", response_model=ConversationRead)
async def update_conversation(
    conversation_id: int,
    payload: ConversationUpdate,
    db: DbSession,
    current_user: CurrentUserDep,
) -> Conversation:
    """Rename a conversation (or update its status). Only the title field is
    exposed in the UI today; the schema also accepts ``status`` for future
    use (archive / pin / etc.)."""
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
    """Hard-delete a conversation and every row it owns.

    The FK columns on messages / agent_runs / memory_summaries don't have
    ``ON DELETE CASCADE`` (the slice-1 migration left them as plain FKs), so
    we tear the dependency graph down manually:

        tool_call_logs → agent_runs → memory_summaries / messages → conversation

    All deletes happen in one transaction so we never leave half-deleted
    state if the user closes the tab mid-request.
    """
    await _require_owned_conversation(db, conversation_id, current_user.id)

    # tool_call_logs FK→agent_runs. Resolve agent_run ids first so we can
    # bulk-delete logs in a single query without joining inside the DELETE.
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
