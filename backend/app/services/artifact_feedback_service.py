from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artifact_feedback_event import ArtifactFeedbackEvent
from app.models.user import User
from app.schemas.artifact_feedback import ArtifactFeedbackCreate
from app.services.user_scope_service import get_generated_artifact_for_user_or_404

ALLOWED_FEEDBACK_TYPES = {
    "accepted",
    "edited_then_used",
    "rejected",
    "saved_for_later",
}


def ensure_feedback_type_allowed(feedback_type: str) -> None:
    if feedback_type not in ALLOWED_FEEDBACK_TYPES:
        raise HTTPException(status_code=400, detail="Invalid feedback_type")


async def create_artifact_feedback(
    db: AsyncSession,
    artifact_id: int,
    payload: ArtifactFeedbackCreate,
    current_user: User | None = None,
) -> ArtifactFeedbackEvent:
    if current_user is None:
        raise HTTPException(status_code=500, detail="Current user scope is required")
    await get_generated_artifact_for_user_or_404(db, artifact_id, current_user)
    ensure_feedback_type_allowed(payload.feedback_type)

    feedback = ArtifactFeedbackEvent(
        generated_artifact_id=artifact_id,
        feedback_type=payload.feedback_type,
        note=payload.note,
    )
    db.add(feedback)
    await db.commit()
    await db.refresh(feedback)
    return feedback


async def list_artifact_feedback(
    db: AsyncSession,
    artifact_id: int,
    limit: int,
    offset: int,
    current_user: User | None = None,
) -> list[ArtifactFeedbackEvent]:
    if current_user is None:
        raise HTTPException(status_code=500, detail="Current user scope is required")
    await get_generated_artifact_for_user_or_404(db, artifact_id, current_user)

    statement = (
        select(ArtifactFeedbackEvent)
        .where(ArtifactFeedbackEvent.generated_artifact_id == artifact_id)
        .order_by(
            ArtifactFeedbackEvent.created_at.desc(),
            ArtifactFeedbackEvent.id.desc(),
        )
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(statement)
    return list(result.scalars().all())
