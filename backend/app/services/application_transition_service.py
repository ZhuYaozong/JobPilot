from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application_event import ApplicationEvent
from app.models.application_record import ApplicationRecord
from app.schemas.application_event import ApplicationTransitionRequest


async def transition_application_stage(
    db: AsyncSession,
    application_id: int,
    payload: ApplicationTransitionRequest,
) -> ApplicationRecord:
    application = await db.get(ApplicationRecord, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application record not found")

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
