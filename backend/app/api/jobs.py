from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.job_posting import JobPosting
from app.schemas.job_posting import (
    JobPostingCreate,
    JobPostingListItem,
    JobPostingRead,
    JobPostingUpdate,
)
from app.services.job_parsing_service import parse_job_posting

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


async def get_job_or_404(db: AsyncSession, job_id: int) -> JobPosting:
    # 统一处理不存在的岗位，避免每个接口重复写 404 判断。
    job = await db.get(JobPosting, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job posting not found")
    return job


@router.post("", response_model=JobPostingRead, status_code=201)
async def create_job(
    payload: JobPostingCreate,
    db: AsyncSession = Depends(get_db),
) -> JobPosting:
    job = JobPosting(**payload.model_dump())
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


@router.get("", response_model=list[JobPostingListItem])
async def list_jobs(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[JobPosting]:
    statement = (
        select(JobPosting)
        .order_by(JobPosting.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(statement)
    return list(result.scalars().all())


@router.get("/{job_id}", response_model=JobPostingRead)
async def read_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
) -> JobPosting:
    return await get_job_or_404(db, job_id)


@router.post("/{job_id}/parse", response_model=JobPostingRead)
async def parse_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
) -> JobPosting:
    job = await get_job_or_404(db, job_id)
    return await parse_job_posting(db, job)


@router.patch("/{job_id}", response_model=JobPostingRead)
async def update_job(
    job_id: int,
    payload: JobPostingUpdate,
    db: AsyncSession = Depends(get_db),
) -> JobPosting:
    job = await get_job_or_404(db, job_id)
    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(job, field, value)

    await db.commit()
    await db.refresh(job)
    return job
