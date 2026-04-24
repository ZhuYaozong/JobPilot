from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUserDep, ListLimit, ListOffset
from app.db.session import get_db
from app.models.generated_artifact import GeneratedArtifact
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
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUserDep = None,
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
    limit: ListLimit = 20,
    offset: ListOffset = 0,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUserDep = None,
) -> list[GeneratedArtifact]:
    # GeneratedArtifact 列表明确采用 created_at recent-first，优先展示最近生成或写入的材料。
    statement = (
        select(GeneratedArtifact)
        .where(GeneratedArtifact.user_id == current_user.id)
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
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUserDep = None,
) -> GeneratedArtifact:
    return await generate_cover_letter(db, payload, current_user=current_user)


@router.post(
    "/generate-interview-prep",
    response_model=GeneratedArtifactRead,
    status_code=201,
)
async def generate_interview_prep_artifact(
    payload: InterviewPrepGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUserDep = None,
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
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUserDep = None,
):
    return await create_artifact_feedback(db, artifact_id, payload, current_user)


@router.get("/{artifact_id}/feedback", response_model=list[ArtifactFeedbackListItem])
async def list_feedback_for_artifact(
    artifact_id: int,
    limit: ListLimit = 20,
    offset: ListOffset = 0,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUserDep = None,
):
    return await list_artifact_feedback(db, artifact_id, limit, offset, current_user)


@router.get("/{artifact_id}", response_model=GeneratedArtifactRead)
async def read_artifact(
    artifact_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUserDep = None,
) -> GeneratedArtifact:
    return await get_generated_artifact_for_user_or_404(db, artifact_id, current_user)


@router.patch("/{artifact_id}", response_model=GeneratedArtifactRead)
async def update_artifact(
    artifact_id: int,
    payload: GeneratedArtifactUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUserDep = None,
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
