from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUserDep, DbSession, ListLimit, ListOffset
from app.models.generated_artifact import GeneratedArtifact
from app.models.artifact_feedback_event import ArtifactFeedbackEvent
from app.models.user import User
from app.schemas.artifact_feedback import (
    ArtifactFeedbackCreate,
    ArtifactFeedbackListItem,
    ArtifactFeedbackRead,
)
from app.schemas.cover_letter_generation import CoverLetterGenerateRequest
from app.schemas.generated_artifact import (
    GeneratedArtifactCreate,
    GeneratedArtifactListItem,
    GeneratedArtifactRead,
    GeneratedArtifactUpdate,
)
from app.schemas.interview_prep_generation import InterviewPrepGenerateRequest
from app.services.artifact_feedback_service import (
    create_artifact_feedback,
    list_artifact_feedback,
)
from app.services.cover_letter_service import generate_cover_letter
from app.services.export_service import (
    SUPPORTED_FORMATS,
    build_content_disposition,
    export_docx,
    export_markdown,
)
from app.services.interview_prep_service import generate_interview_prep
from app.services.user_scope_service import (
    get_application_record_for_user_or_404,
    get_generated_artifact_for_user_or_404,
    get_job_posting_for_user_or_404,
    get_resume_for_user_or_404,
)

router = APIRouter(prefix="/api/v1/artifacts", tags=["artifacts"])


def ensure_artifact_has_business_link(
    resume_id: int | None,
    job_posting_id: int | None,
    application_record_id: int | None,
) -> None:
    if resume_id is None and job_posting_id is None and application_record_id is None:
        raise HTTPException(
            status_code=400,
            detail="Generated artifact must link to at least one business object",
        )


async def ensure_business_links_exist(
    db: AsyncSession,
    resume_id: int | None,
    job_posting_id: int | None,
    application_record_id: int | None,
    current_user: User,
) -> None:
    if resume_id is not None:
        await get_resume_for_user_or_404(db, resume_id, current_user)

    if job_posting_id is not None:
        await get_job_posting_for_user_or_404(db, job_posting_id, current_user)

    if application_record_id is not None:
        await get_application_record_for_user_or_404(
            db,
            application_record_id,
            current_user,
        )


@router.post("", response_model=GeneratedArtifactRead, status_code=201)
async def create_artifact(
    payload: GeneratedArtifactCreate,
    db: DbSession,
    current_user: CurrentUserDep,
) -> GeneratedArtifact:
    ensure_artifact_has_business_link(
        payload.resume_id,
        payload.job_posting_id,
        payload.application_record_id,
    )
    await ensure_business_links_exist(
        db,
        resume_id=payload.resume_id,
        job_posting_id=payload.job_posting_id,
        application_record_id=payload.application_record_id,
        current_user=current_user,
    )

    artifact = GeneratedArtifact(user_id=current_user.id, **payload.model_dump())
    db.add(artifact)
    await db.commit()
    await db.refresh(artifact)
    return artifact


@router.get("", response_model=list[GeneratedArtifactListItem])
async def list_artifacts(
    db: DbSession,
    current_user: CurrentUserDep,
    limit: ListLimit = 20,
    offset: ListOffset = 0,
    resume_id: int | None = Query(None, ge=1, description="按简历 ID 过滤。"),
    job_posting_id: int | None = Query(None, ge=1, description="按岗位 ID 过滤。"),
    artifact_type: str | None = Query(None, min_length=1, max_length=50),
) -> list[GeneratedArtifact]:
    # GeneratedArtifact 列表明确采用 created_at recent-first，优先展示最近生成或写入的材料。
    filters = [GeneratedArtifact.user_id == current_user.id]
    if resume_id is not None:
        filters.append(GeneratedArtifact.resume_id == resume_id)
    if job_posting_id is not None:
        filters.append(GeneratedArtifact.job_posting_id == job_posting_id)
    if artifact_type is not None:
        filters.append(GeneratedArtifact.artifact_type == artifact_type.strip()[:50])

    statement = (
        select(GeneratedArtifact)
        .where(*filters)
        .order_by(GeneratedArtifact.created_at.desc(), GeneratedArtifact.id.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(statement)
    return list(result.scalars().all())


@router.post(
    "/generate-cover-letter",
    response_model=GeneratedArtifactRead,
    status_code=201,
)
async def generate_cover_letter_artifact(
    payload: CoverLetterGenerateRequest,
    db: DbSession,
    current_user: CurrentUserDep,
) -> GeneratedArtifact:
    return await generate_cover_letter(db, payload, current_user=current_user)


@router.post(
    "/generate-interview-prep",
    response_model=GeneratedArtifactRead,
    status_code=201,
)
async def generate_interview_prep_artifact(
    payload: InterviewPrepGenerateRequest,
    db: DbSession,
    current_user: CurrentUserDep,
) -> GeneratedArtifact:
    return await generate_interview_prep(db, payload, current_user=current_user)


@router.post(
    "/{artifact_id}/feedback",
    response_model=ArtifactFeedbackRead,
    status_code=201,
)
async def create_feedback_for_artifact(
    artifact_id: int,
    payload: ArtifactFeedbackCreate,
    db: DbSession,
    current_user: CurrentUserDep,
):
    return await create_artifact_feedback(db, artifact_id, payload, current_user)


@router.get("/{artifact_id}/feedback", response_model=list[ArtifactFeedbackListItem])
async def list_feedback_for_artifact(
    artifact_id: int,
    db: DbSession,
    current_user: CurrentUserDep,
    limit: ListLimit = 20,
    offset: ListOffset = 0,
):
    return await list_artifact_feedback(db, artifact_id, limit, offset, current_user)


@router.get("/{artifact_id}", response_model=GeneratedArtifactRead)
async def read_artifact(
    artifact_id: int,
    db: DbSession,
    current_user: CurrentUserDep,
) -> GeneratedArtifact:
    return await get_generated_artifact_for_user_or_404(db, artifact_id, current_user)


@router.get("/{artifact_id}/export")
async def export_artifact(
    artifact_id: int,
    db: DbSession,
    current_user: CurrentUserDep,
    format: str = Query("markdown", description="markdown | docx"),
) -> Response:
    """把求职材料(cover letter / interview prep / 其它)正文渲染成可下载文件。"""
    if format not in SUPPORTED_FORMATS:
        raise HTTPException(status_code=400, detail="Unsupported export format")

    artifact = await get_generated_artifact_for_user_or_404(
        db, artifact_id, current_user,
    )
    body = artifact.content_text or ""
    if not body.strip():
        raise HTTPException(status_code=400, detail="Artifact has no content to export")

    title = (artifact.title or f"artifact-{artifact.id}").strip()
    payload = (
        export_markdown(title, body)
        if format == "markdown"
        else export_docx(title, body)
    )
    return Response(
        content=payload.content,
        media_type=payload.media_type,
        headers={"Content-Disposition": build_content_disposition(payload.filename)},
    )


@router.patch("/{artifact_id}", response_model=GeneratedArtifactRead)
async def update_artifact(
    artifact_id: int,
    payload: GeneratedArtifactUpdate,
    db: DbSession,
    current_user: CurrentUserDep,
) -> GeneratedArtifact:
    artifact = await get_generated_artifact_for_user_or_404(db, artifact_id, current_user)
    update_data = payload.model_dump(exclude_unset=True)

    resume_id = update_data.get("resume_id", artifact.resume_id)
    job_posting_id = update_data.get("job_posting_id", artifact.job_posting_id)
    application_record_id = update_data.get(
        "application_record_id",
        artifact.application_record_id,
    )

    ensure_artifact_has_business_link(
        resume_id,
        job_posting_id,
        application_record_id,
    )

    await ensure_business_links_exist(
        db,
        resume_id=resume_id if "resume_id" in update_data else None,
        job_posting_id=job_posting_id if "job_posting_id" in update_data else None,
        application_record_id=(
            application_record_id if "application_record_id" in update_data else None
        ),
        current_user=current_user,
    )

    for field, value in update_data.items():
        setattr(artifact, field, value)

    await db.commit()
    await db.refresh(artifact)
    return artifact


@router.delete("/{artifact_id}", status_code=204)
async def delete_artifact(
    artifact_id: int,
    db: DbSession,
    current_user: CurrentUserDep,
) -> Response:
    artifact = await get_generated_artifact_for_user_or_404(
        db, artifact_id, current_user,
    )
    await db.execute(
        delete(ArtifactFeedbackEvent).where(
            ArtifactFeedbackEvent.generated_artifact_id == artifact.id,
        ),
    )
    await db.delete(artifact)
    await db.commit()
    return Response(status_code=204)
