from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUserDep, ListLimit, ListOffset
from app.db.session import get_db
from app.models.job_posting import JobPosting
from app.schemas.job_posting import (
    JobPostingCreate,
    JobPostingListItem,
    JobPostingRead,
    JobPostingUpdate,
)
from app.services.job_parsing_service import parse_job_posting
from app.services.resource_deletion_service import delete_job_posting_tree
from app.services.user_scope_service import get_job_posting_for_user_or_404

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.post("", response_model=JobPostingRead, status_code=201)
async def create_job(
    payload: JobPostingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUserDep = None,
) -> JobPosting:
    job = JobPosting(user_id=current_user.id, **payload.model_dump())
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


@router.get("", response_model=list[JobPostingListItem])
async def list_jobs(
    limit: ListLimit = 20,
    offset: ListOffset = 0,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUserDep = None,
) -> list[JobPosting]:
    # Jobs 列表明确采用 updated_at recent-first，避免前端靠隐含顺序猜测“最近岗位”。
    statement = (
        select(JobPosting)
        .where(JobPosting.user_id == current_user.id)
        .order_by(JobPosting.updated_at.desc(), JobPosting.id.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(statement)
    return list(result.scalars().all())


@router.get("/{job_id}", response_model=JobPostingRead)
async def read_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUserDep = None,
) -> JobPosting:
    return await get_job_posting_for_user_or_404(db, job_id, current_user)


@router.post("/{job_id}/parse", response_model=JobPostingRead)
async def parse_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUserDep = None,
) -> JobPosting:
    job = await get_job_posting_for_user_or_404(db, job_id, current_user)
    return await parse_job_posting(db, job)


@router.patch("/{job_id}", response_model=JobPostingRead)
async def update_job(
    job_id: int,
    payload: JobPostingUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUserDep = None,
) -> JobPosting:
    job = await get_job_posting_for_user_or_404(db, job_id, current_user)
    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(job, field, value)

    await db.commit()
    await db.refresh(job)
    return job


@router.delete("/{job_id}", status_code=204)
async def delete_job(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUserDep = None,
) -> None:
    job = await get_job_posting_for_user_or_404(db, job_id, current_user)
    await delete_job_posting_tree(db, job, current_user)
