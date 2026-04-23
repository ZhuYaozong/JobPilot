from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.artifact_feedback_event import ArtifactFeedbackEvent
from app.models.generated_artifact import GeneratedArtifact
from app.schemas.artifact_feedback import ArtifactFeedbackCreate

ALLOWED_FEEDBACK_TYPES = {
    "accepted",
    "edited_then_used",
    "rejected",
    "saved_for_later",
}


async def ensure_artifact_exists(
    db: AsyncSession,
    artifact_id: int,
) -> GeneratedArtifact:
    artifact = await db.get(GeneratedArtifact, artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Generated artifact not found")
    return artifact


def ensure_feedback_type_allowed(feedback_type: str) -> None:
    if feedback_type not in ALLOWED_FEEDBACK_TYPES:
        raise HTTPException(status_code=400, detail="Invalid feedback_type")


async def create_artifact_feedback(
    db: AsyncSession,
    artifact_id: int,
    payload: ArtifactFeedbackCreate,
) -> ArtifactFeedbackEvent:
    await ensure_artifact_exists(db, artifact_id)
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
) -> list[ArtifactFeedbackEvent]:
    await ensure_artifact_exists(db, artifact_id)

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
