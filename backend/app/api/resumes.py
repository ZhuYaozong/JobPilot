from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.resume import Resume
from app.schemas.resume import ResumeCreate, ResumeListItem, ResumeRead, ResumeUpdate
from app.services.resume_parsing_service import parse_resume

router = APIRouter(prefix="/api/v1/resumes", tags=["resumes"])


async def get_resume_or_404(db: AsyncSession, resume_id: int) -> Resume:
    # 统一处理不存在的简历，避免每个接口重复写 404 判断。
    resume = await db.get(Resume, resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")
    return resume


@router.post("", response_model=ResumeRead, status_code=201)
async def create_resume(
    payload: ResumeCreate,
    db: AsyncSession = Depends(get_db),
) -> Resume:
    resume = Resume(**payload.model_dump())
    db.add(resume)
    await db.commit()
    await db.refresh(resume)
    return resume


@router.get("", response_model=list[ResumeListItem])
async def list_resumes(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[Resume]:
    statement = (
        select(Resume)
        .order_by(Resume.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(statement)
    return list(result.scalars().all())


@router.get("/{resume_id}", response_model=ResumeRead)
async def read_resume(
    resume_id: int,
    db: AsyncSession = Depends(get_db),
) -> Resume:
    return await get_resume_or_404(db, resume_id)


@router.post("/{resume_id}/parse", response_model=ResumeRead)
async def parse_resume_detail(
    resume_id: int,
    db: AsyncSession = Depends(get_db),
) -> Resume:
    resume = await get_resume_or_404(db, resume_id)
    return await parse_resume(db, resume)


@router.patch("/{resume_id}", response_model=ResumeRead)
async def update_resume(
    resume_id: int,
    payload: ResumeUpdate,
    db: AsyncSession = Depends(get_db),
) -> Resume:
    resume = await get_resume_or_404(db, resume_id)
    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(resume, field, value)

    await db.commit()
    await db.refresh(resume)
    return resume
