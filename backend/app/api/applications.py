from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUserDep, ListLimit, ListOffset
from app.db.session import get_db
from app.models.application_record import ApplicationRecord
from app.schemas.application_record import (
    ApplicationRecordCreate,
    ApplicationRecordListItem,
    ApplicationRecordRead,
    ApplicationRecordUpdate,
)
from app.services.user_scope_service import (
    ensure_resume_and_job_exist_for_user,
    get_application_record_for_user_or_404,
)

router = APIRouter(prefix="/api/v1/applications", tags=["applications"])


@router.post("", response_model=ApplicationRecordRead, status_code=201)
async def create_application(
    payload: ApplicationRecordCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUserDep = None,
) -> ApplicationRecord:
    await ensure_resume_and_job_exist_for_user(
        db,
        resume_id=payload.resume_id,
        job_posting_id=payload.job_posting_id,
        current_user=current_user,
    )

    application = ApplicationRecord(user_id=current_user.id, **payload.model_dump())
    db.add(application)
    await db.commit()
    await db.refresh(application)
    return application


@router.get("", response_model=list[ApplicationRecordListItem])
async def list_applications(
    limit: ListLimit = 20,
    offset: ListOffset = 0,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUserDep = None,
) -> list[ApplicationRecord]:
    # ApplicationRecord 列表明确采用 updated_at recent-first，优先展示最近推进过的投递。
    statement = (
        select(ApplicationRecord)
        .where(ApplicationRecord.user_id == current_user.id)
        .order_by(ApplicationRecord.updated_at.desc(), ApplicationRecord.id.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(statement)
    return list(result.scalars().all())


@router.get("/{application_id}", response_model=ApplicationRecordRead)
async def read_application(
    application_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUserDep = None,
) -> ApplicationRecord:
    return await get_application_record_for_user_or_404(
        db,
        application_id,
        current_user,
    )


@router.patch("/{application_id}", response_model=ApplicationRecordRead)
async def update_application(
    application_id: int,
    payload: ApplicationRecordUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUserDep = None,
) -> ApplicationRecord:
    application = await get_application_record_for_user_or_404(
        db,
        application_id,
        current_user,
    )
    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(application, field, value)

    await db.commit()
    await db.refresh(application)
    return application
