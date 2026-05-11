from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import CurrentUserDep, DbSession, ListLimit, ListOffset
from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.conversation import ConversationListItem
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
    owned = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        ),
    )
    if owned.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    statement = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.sequence_no.asc(), Message.id.asc())
    )
    result = await db.execute(statement)
    return list(result.scalars().all())
