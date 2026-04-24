from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUserDep, ListLimit, ListOffset
from app.db.session import get_db
from app.models.resume import Resume
from app.models.resume_version import ResumeVersion
from app.models.user import User
from app.schemas.resume_version import (
    ResumeVersionCreate,
    ResumeVersionListItem,
    ResumeVersionRead,
    ResumeVersionUpdate,
)
from app.services.user_scope_service import (
    get_job_posting_for_user_or_404,
    get_resume_for_user_or_404,
)

router = APIRouter(tags=["resume-versions"])


async def get_resume_version_or_404(
    db: AsyncSession,
    version_id: int,
    current_user: User,
) -> ResumeVersion:
    statement = (
        select(ResumeVersion)
        .join(Resume, Resume.id == ResumeVersion.resume_id)
        .where(
            ResumeVersion.id == version_id,
            Resume.user_id == current_user.id,
        )
    )
    result = await db.execute(statement)
    version = result.scalar_one_or_none()
    if version is None:
        raise HTTPException(status_code=404, detail="Resume version not found")
    return version


async def ensure_job_exists_if_present(
    db: AsyncSession,
    job_posting_id: int | None,
    current_user: User,
) -> None:
    if job_posting_id is None:
        return

    await get_job_posting_for_user_or_404(db, job_posting_id, current_user)


@router.post("/api/v1/resume-versions", response_model=ResumeVersionRead, status_code=201)
async def create_resume_version(
    payload: ResumeVersionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUserDep = None,
) -> ResumeVersion:
    await get_resume_for_user_or_404(db, payload.resume_id, current_user)
    await ensure_job_exists_if_present(db, payload.job_posting_id, current_user)

    version = ResumeVersion(**payload.model_dump())
    db.add(version)
    await db.commit()
    await db.refresh(version)
    return version


@router.get("/api/v1/resume-versions", response_model=list[ResumeVersionListItem])
async def list_resume_versions(
    limit: ListLimit = 20,
    offset: ListOffset = 0,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUserDep = None,
) -> list[ResumeVersion]:
    statement = (
        select(ResumeVersion)
        .join(Resume, Resume.id == ResumeVersion.resume_id)
        .where(Resume.user_id == current_user.id)
        .order_by(ResumeVersion.created_at.desc(), ResumeVersion.id.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(statement)
    return list(result.scalars().all())


@router.get("/api/v1/resume-versions/{version_id}", response_model=ResumeVersionRead)
async def read_resume_version(
    version_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUserDep = None,
) -> ResumeVersion:
    return await get_resume_version_or_404(db, version_id, current_user)


@router.patch("/api/v1/resume-versions/{version_id}", response_model=ResumeVersionRead)
async def update_resume_version(
    version_id: int,
    payload: ResumeVersionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUserDep = None,
) -> ResumeVersion:
    version = await get_resume_version_or_404(db, version_id, current_user)
    update_data = payload.model_dump(exclude_unset=True)

    if "job_posting_id" in update_data:
        await ensure_job_exists_if_present(db, update_data["job_posting_id"], current_user)

    for field, value in update_data.items():
        setattr(version, field, value)

    await db.commit()
    await db.refresh(version)
    return version


@router.get(
    "/api/v1/resumes/{resume_id}/versions",
    response_model=list[ResumeVersionListItem],
)
async def list_versions_by_resume(
    resume_id: int,
    limit: ListLimit = 20,
    offset: ListOffset = 0,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUserDep = None,
) -> list[ResumeVersion]:
    await get_resume_for_user_or_404(db, resume_id, current_user)

    statement = (
        select(ResumeVersion)
        .where(ResumeVersion.resume_id == resume_id)
        .order_by(ResumeVersion.created_at.desc(), ResumeVersion.id.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(statement)
    return list(result.scalars().all())
