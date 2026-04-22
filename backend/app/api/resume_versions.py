from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.job_posting import JobPosting
from app.models.resume import Resume
from app.models.resume_version import ResumeVersion
from app.schemas.resume_version import (
    ResumeVersionCreate,
    ResumeVersionListItem,
    ResumeVersionRead,
    ResumeVersionUpdate,
)

router = APIRouter(tags=["resume-versions"])


async def get_resume_version_or_404(
    db: AsyncSession,
    version_id: int,
) -> ResumeVersion:
    # 统一处理不存在的简历版本，保持和现有模块相同的 404 风格。
    version = await db.get(ResumeVersion, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Resume version not found")
    return version


async def ensure_resume_exists(db: AsyncSession, resume_id: int) -> None:
    resume = await db.get(Resume, resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")


async def ensure_job_exists_if_present(
    db: AsyncSession,
    job_posting_id: int | None,
) -> None:
    if job_posting_id is None:
        return

    job = await db.get(JobPosting, job_posting_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job posting not found")


@router.post("/api/v1/resume-versions", response_model=ResumeVersionRead, status_code=201)
async def create_resume_version(
    payload: ResumeVersionCreate,
    db: AsyncSession = Depends(get_db),
) -> ResumeVersion:
    await ensure_resume_exists(db, payload.resume_id)
    await ensure_job_exists_if_present(db, payload.job_posting_id)

    version = ResumeVersion(**payload.model_dump())
    db.add(version)
    await db.commit()
    await db.refresh(version)
    return version


@router.get("/api/v1/resume-versions", response_model=list[ResumeVersionListItem])
async def list_resume_versions(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[ResumeVersion]:
    statement = (
        select(ResumeVersion)
        .order_by(ResumeVersion.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(statement)
    return list(result.scalars().all())


@router.get("/api/v1/resume-versions/{version_id}", response_model=ResumeVersionRead)
async def read_resume_version(
    version_id: int,
    db: AsyncSession = Depends(get_db),
) -> ResumeVersion:
    return await get_resume_version_or_404(db, version_id)


@router.patch("/api/v1/resume-versions/{version_id}", response_model=ResumeVersionRead)
async def update_resume_version(
    version_id: int,
    payload: ResumeVersionUpdate,
    db: AsyncSession = Depends(get_db),
) -> ResumeVersion:
    version = await get_resume_version_or_404(db, version_id)
    update_data = payload.model_dump(exclude_unset=True)

    if "job_posting_id" in update_data:
        await ensure_job_exists_if_present(db, update_data["job_posting_id"])

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
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[ResumeVersion]:
    await ensure_resume_exists(db, resume_id)

    statement = (
        select(ResumeVersion)
        .where(ResumeVersion.resume_id == resume_id)
        .order_by(ResumeVersion.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(statement)
    return list(result.scalars().all())
