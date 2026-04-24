from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUserDep, ListLimit, ListOffset
from app.db.session import get_db
from app.models.resume import Resume
from app.schemas.resume import ResumeCreate, ResumeListItem, ResumeRead, ResumeUpdate
from app.services.resume_parsing_service import parse_resume
from app.services.user_scope_service import get_resume_for_user_or_404

router = APIRouter(prefix="/api/v1/resumes", tags=["resumes"])


@router.post("", response_model=ResumeRead, status_code=201)
async def create_resume(
    payload: ResumeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUserDep = None,
) -> Resume:
    resume = Resume(user_id=current_user.id, **payload.model_dump())
    db.add(resume)
    await db.commit()
    await db.refresh(resume)
    return resume


@router.get("", response_model=list[ResumeListItem])
async def list_resumes(
    limit: ListLimit = 20,
    offset: ListOffset = 0,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUserDep = None,
) -> list[Resume]:
    # Resumes 列表明确采用 updated_at recent-first，让最近编辑/解析过的简历优先出现。
    statement = (
        select(Resume)
        .where(Resume.user_id == current_user.id)
        .order_by(Resume.updated_at.desc(), Resume.id.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(statement)
    return list(result.scalars().all())


@router.get("/{resume_id}", response_model=ResumeRead)
async def read_resume(
    resume_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUserDep = None,
) -> Resume:
    return await get_resume_for_user_or_404(db, resume_id, current_user)


@router.post("/{resume_id}/parse", response_model=ResumeRead)
async def parse_resume_detail(
    resume_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUserDep = None,
) -> Resume:
    resume = await get_resume_for_user_or_404(db, resume_id, current_user)
    return await parse_resume(db, resume)


@router.patch("/{resume_id}", response_model=ResumeRead)
async def update_resume(
    resume_id: int,
    payload: ResumeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUserDep = None,
) -> Resume:
    resume = await get_resume_for_user_or_404(db, resume_id, current_user)
    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(resume, field, value)

    await db.commit()
    await db.refresh(resume)
    return resume
