from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.job_posting import JobPosting
from app.models.match_result import MatchResult
from app.models.resume import Resume
from app.schemas.match_result import (
    MatchResultCreate,
    MatchResultListItem,
    MatchResultRead,
    MatchResultUpdate,
)

router = APIRouter(prefix="/api/v1/matches", tags=["matches"])


async def get_match_or_404(db: AsyncSession, match_id: int) -> MatchResult:
    # 统一处理不存在的匹配记录，保持和现有模块相同的 404 风格。
    match = await db.get(MatchResult, match_id)
    if match is None:
        raise HTTPException(status_code=404, detail="Match result not found")
    return match


async def ensure_resume_and_job_exist(
    db: AsyncSession,
    resume_id: int,
    job_posting_id: int,
) -> None:
    # 创建匹配记录前只检查外键是否存在，不做复杂联表加载。
    resume = await db.get(Resume, resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")

    job = await db.get(JobPosting, job_posting_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job posting not found")


@router.post("", response_model=MatchResultRead, status_code=201)
async def create_match(
    payload: MatchResultCreate,
    db: AsyncSession = Depends(get_db),
) -> MatchResult:
    await ensure_resume_and_job_exist(
        db,
        resume_id=payload.resume_id,
        job_posting_id=payload.job_posting_id,
    )

    match = MatchResult(**payload.model_dump())
    db.add(match)
    await db.commit()
    await db.refresh(match)
    return match


@router.get("", response_model=list[MatchResultListItem])
async def list_matches(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[MatchResult]:
    statement = (
        select(MatchResult)
        .order_by(MatchResult.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(statement)
    return list(result.scalars().all())


@router.get("/{match_id}", response_model=MatchResultRead)
async def read_match(
    match_id: int,
    db: AsyncSession = Depends(get_db),
) -> MatchResult:
    return await get_match_or_404(db, match_id)


@router.patch("/{match_id}", response_model=MatchResultRead)
async def update_match(
    match_id: int,
    payload: MatchResultUpdate,
    db: AsyncSession = Depends(get_db),
) -> MatchResult:
    match = await get_match_or_404(db, match_id)
    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(match, field, value)

    await db.commit()
    await db.refresh(match)
    return match
