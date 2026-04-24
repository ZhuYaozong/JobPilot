from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application_event import ApplicationEvent
from app.models.application_record import ApplicationRecord
from app.models.user import User
from app.schemas.application_event import ApplicationTransitionRequest
from app.services.user_scope_service import get_application_record_for_user_or_404


async def transition_application_stage(
    db: AsyncSession,
    application_id: int,
    payload: ApplicationTransitionRequest,
    current_user: User | None = None,
) -> ApplicationRecord:
    if current_user is None:
        raise HTTPException(status_code=500, detail="Current user scope is required")
    application = await get_application_record_for_user_or_404(
        db,
        application_id,
        current_user,
    )

    old_stage = application.current_stage
    application.current_stage = payload.target_stage

    update_data = payload.model_dump(
        include={"next_action", "next_action_at", "notes"},
        exclude_unset=True,
    )
    for field, value in update_data.items():
        setattr(application, field, value)

    event = ApplicationEvent(
        application_record_id=application.id,
        event_type="stage_changed",
        from_stage=old_stage,
        to_stage=payload.target_stage,
        event_at=payload.event_at,
        operator_type=payload.operator_type,
        payload_json=payload.payload_json,
        note=payload.note,
    )
    db.add(event)

    await db.commit()
    await db.refresh(application)
    return application
