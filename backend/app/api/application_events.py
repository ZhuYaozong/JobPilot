from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentUserDep, DbSession, ListLimit, ListOffset
from app.models.application_event import ApplicationEvent
from app.schemas.application_event import (
    ApplicationEventRead,
    ApplicationTransitionRequest,
)
from app.schemas.application_record import ApplicationRecordRead
from app.services.application_transition_service import transition_application_stage
from app.services.user_scope_service import get_application_record_for_user_or_404

router = APIRouter(prefix="/api/v1/applications", tags=["applications"])


@router.get("/{application_id}/events", response_model=list[ApplicationEventRead])
async def list_application_events(
    application_id: int,
    db: DbSession,
    current_user: CurrentUserDep,
    limit: ListLimit = 20,
    offset: ListOffset = 0,
) -> list[ApplicationEvent]:
    application = await get_application_record_for_user_or_404(
        db,
        application_id,
        current_user,
    )

    statement = (
        select(ApplicationEvent)
        .where(ApplicationEvent.application_record_id == application.id)
        .order_by(ApplicationEvent.created_at.desc(), ApplicationEvent.id.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(statement)
    return list(result.scalars().all())


@router.post("/{application_id}/transition", response_model=ApplicationRecordRead)
async def transition_application(
    application_id: int,
    payload: ApplicationTransitionRequest,
    db: DbSession,
    current_user: CurrentUserDep,
):
    return await transition_application_stage(
        db,
        application_id,
        payload,
        current_user=current_user,
    )
