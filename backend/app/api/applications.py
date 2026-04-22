from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.application_record import ApplicationRecord
from app.models.job_posting import JobPosting
from app.models.resume import Resume
from app.schemas.application_record import (
    ApplicationRecordCreate,
    ApplicationRecordListItem,
    ApplicationRecordRead,
    ApplicationRecordUpdate,
)

router = APIRouter(prefix="/api/v1/applications", tags=["applications"])


async def get_application_or_404(
    db: AsyncSession,
    application_id: int,
) -> ApplicationRecord:
    # 统一处理不存在的投递记录，保持和现有模块相同的 404 风格。
    application = await db.get(ApplicationRecord, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application record not found")
    return application


async def ensure_resume_and_job_exist(
    db: AsyncSession,
    resume_id: int,
    job_posting_id: int,
) -> None:
    # 创建投递记录前只检查外键是否存在，不做复杂联表加载。
    resume = await db.get(Resume, resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")

    job = await db.get(JobPosting, job_posting_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job posting not found")


@router.post("", response_model=ApplicationRecordRead, status_code=201)
async def create_application(
    payload: ApplicationRecordCreate,
    db: AsyncSession = Depends(get_db),
) -> ApplicationRecord:
    await ensure_resume_and_job_exist(
        db,
        resume_id=payload.resume_id,
        job_posting_id=payload.job_posting_id,
    )

    application = ApplicationRecord(**payload.model_dump())
    db.add(application)
    await db.commit()
    await db.refresh(application)
    return application


@router.get("", response_model=list[ApplicationRecordListItem])
async def list_applications(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[ApplicationRecord]:
    statement = (
        select(ApplicationRecord)
        .order_by(ApplicationRecord.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(statement)
    return list(result.scalars().all())


@router.get("/{application_id}", response_model=ApplicationRecordRead)
async def read_application(
    application_id: int,
    db: AsyncSession = Depends(get_db),
) -> ApplicationRecord:
    return await get_application_or_404(db, application_id)


@router.patch("/{application_id}", response_model=ApplicationRecordRead)
async def update_application(
    application_id: int,
    payload: ApplicationRecordUpdate,
    db: AsyncSession = Depends(get_db),
) -> ApplicationRecord:
    application = await get_application_or_404(db, application_id)
    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(application, field, value)

    await db.commit()
    await db.refresh(application)
    return application
