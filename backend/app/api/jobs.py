from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import CurrentUserDep, DbSession, ListLimit, ListOffset
from app.models.job_posting import JobPosting
from app.schemas.job_draft import JobDraftRequest, JobDraftResponse
from app.schemas.job_posting import (
    JobPostingCreate,
    JobPostingListItem,
    JobPostingRead,
    JobPostingUpdate,
    JobURLFetchPreview,
    JobURLFetchRequest,
)
from app.services.job_draft_service import generate_job_draft
from app.services.job_parsing_service import parse_job_posting
from app.services.job_url_fetcher import JobURLFetchError, fetch_jd_from_url
from app.services.resource_deletion_service import delete_job_posting_tree
from app.services.user_scope_service import get_job_posting_for_user_or_404

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.post("", response_model=JobPostingRead, status_code=201)
async def create_job(
    payload: JobPostingCreate,
    db: DbSession,
    current_user: CurrentUserDep,
) -> JobPosting:
    # exclude_none: parsed_json 在普通 URL/手动模式下不传,走默认 NULL;
    # AI 草稿模式带上 parsed_json,一次落库省一次 LLM 调用。
    job = JobPosting(
        user_id=current_user.id,
        **payload.model_dump(exclude_none=True),
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


@router.post("/fetch-from-url", response_model=JobURLFetchPreview)
async def fetch_job_from_url(
    payload: JobURLFetchRequest,
    current_user: CurrentUserDep,  # noqa: ARG001 — 依赖注入用于保持接口的用户边界。
) -> JobURLFetchPreview:
    """从公开 URL 抓取 JD，并返回预览对象。

    这里不写数据库。前端只用结果预填创建抽屉里的公司、岗位、城市和 JD 字段；
    用户确认后再走常规 POST /jobs 保存。拆成两步可以避免错误抽取留下半成品岗位行。
    """
    try:
        result = await fetch_jd_from_url(payload.url)
    except JobURLFetchError as exc:
        raise HTTPException(status_code=400, detail=exc.user_message) from exc

    return JobURLFetchPreview(
        jd_text=result.jd_text,
        title=result.title,
        company_hint=result.company_hint,
        city_hint=result.city_hint,
        source_url=result.source_url,
    )


@router.post("/draft-from-input", response_model=JobDraftResponse)
async def draft_job_from_input(
    payload: JobDraftRequest,
    current_user: CurrentUserDep,  # noqa: ARG001 — 用户边界
) -> JobDraftResponse:
    """根据用户给的文本或 URL,让 LLM 同时推断岗位基本信息 + 结构化字段。

    不落库,返回 JobDraftResponse 供前端走"预览 → 编辑 → 保存"。
    URL 抓不到时映射成 422,LLM 异常映射成 502,详见 service。
    """
    return await generate_job_draft(payload)


@router.get("", response_model=list[JobPostingListItem])
async def list_jobs(
    db: DbSession,
    current_user: CurrentUserDep,
    limit: ListLimit = 20,
    offset: ListOffset = 0,
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
    db: DbSession,
    current_user: CurrentUserDep,
) -> JobPosting:
    return await get_job_posting_for_user_or_404(db, job_id, current_user)


@router.post("/{job_id}/parse", response_model=JobPostingRead)
async def parse_job(
    job_id: int,
    db: DbSession,
    current_user: CurrentUserDep,
) -> JobPosting:
    job = await get_job_posting_for_user_or_404(db, job_id, current_user)
    return await parse_job_posting(db, job)


@router.patch("/{job_id}", response_model=JobPostingRead)
async def update_job(
    job_id: int,
    payload: JobPostingUpdate,
    db: DbSession,
    current_user: CurrentUserDep,
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
    db: DbSession,
    current_user: CurrentUserDep,
) -> None:
    job = await get_job_posting_for_user_or_404(db, job_id, current_user)
    await delete_job_posting_tree(db, job, current_user)
