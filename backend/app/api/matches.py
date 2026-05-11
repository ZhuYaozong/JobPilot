from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import CurrentUserDep, DbSession, ListLimit, ListOffset
from app.models.match_result import MatchResult
from app.schemas.match_analysis import MatchAnalysisRequest
from app.schemas.match_result import (
    MatchResultCreate,
    MatchResultListItem,
    MatchResultRead,
    MatchResultUpdate,
)
from app.services.match_analysis_service import analyze_match
from app.services.resource_deletion_service import delete_match_result_tree
from app.services.user_scope_service import (
    ensure_resume_and_job_exist_for_user,
    get_match_result_for_user_or_404,
)

router = APIRouter(prefix="/api/v1/matches", tags=["matches"])


@router.post("", response_model=MatchResultRead, status_code=201)
async def create_match(
    payload: MatchResultCreate,
    db: DbSession,
    current_user: CurrentUserDep,
) -> MatchResult:
    await ensure_resume_and_job_exist_for_user(
        db,
        resume_id=payload.resume_id,
        job_posting_id=payload.job_posting_id,
        current_user=current_user,
    )

    match = MatchResult(user_id=current_user.id, **payload.model_dump())
    db.add(match)
    await db.commit()
    await db.refresh(match)
    return match


@router.get("", response_model=list[MatchResultListItem])
async def list_matches(
    db: DbSession,
    current_user: CurrentUserDep,
    limit: ListLimit = 20,
    offset: ListOffset = 0,
) -> list[MatchResult]:
    # MatchResult 列表明确采用 created_at recent-first，因为匹配分析天然按生成时间查看最近结果。
    statement = (
        select(MatchResult)
        .where(MatchResult.user_id == current_user.id)
        .order_by(MatchResult.created_at.desc(), MatchResult.id.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(statement)
    return list(result.scalars().all())


@router.post("/analyze", response_model=MatchResultRead)
async def analyze_match_result(
    payload: MatchAnalysisRequest,
    db: DbSession,
    current_user: CurrentUserDep,
) -> MatchResult:
    return await analyze_match(db, payload, current_user=current_user)


@router.get("/{match_id}", response_model=MatchResultRead)
async def read_match(
    match_id: int,
    db: DbSession,
    current_user: CurrentUserDep,
) -> MatchResult:
    return await get_match_result_for_user_or_404(db, match_id, current_user)


@router.patch("/{match_id}", response_model=MatchResultRead)
async def update_match(
    match_id: int,
    payload: MatchResultUpdate,
    db: DbSession,
    current_user: CurrentUserDep,
) -> MatchResult:
    match = await get_match_result_for_user_or_404(db, match_id, current_user)
    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(match, field, value)

    await db.commit()
    await db.refresh(match)
    return match


@router.delete("/{match_id}", status_code=204)
async def delete_match(
    match_id: int,
    db: DbSession,
    current_user: CurrentUserDep,
) -> None:
    match = await get_match_result_for_user_or_404(db, match_id, current_user)
    await delete_match_result_tree(db, match)
