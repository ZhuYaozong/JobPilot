from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.application_event import ApplicationEvent
from app.models.application_record import ApplicationRecord
from app.schemas.application_event import (
    ApplicationEventRead,
    ApplicationTransitionRequest,
)
from app.schemas.application_record import ApplicationRecordRead
from app.services.application_transition_service import transition_application_stage

router = APIRouter(prefix="/api/v1/applications", tags=["applications"])


@router.get("/{application_id}/events", response_model=list[ApplicationEventRead])
async def list_application_events(
    application_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[ApplicationEvent]:
    application = await db.get(ApplicationRecord, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application record not found")

    statement = (
        select(ApplicationEvent)
        .where(ApplicationEvent.application_record_id == application_id)
        .order_by(ApplicationEvent.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(statement)
    return list(result.scalars().all())


@router.post("/{application_id}/transition", response_model=ApplicationRecordRead)
async def transition_application(
    application_id: int,
    payload: ApplicationTransitionRequest,
    db: AsyncSession = Depends(get_db),
):
    return await transition_application_stage(db, application_id, payload)
