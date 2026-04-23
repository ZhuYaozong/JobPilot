from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.application_record import ApplicationRecord
from app.models.generated_artifact import GeneratedArtifact
from app.models.job_posting import JobPosting
from app.models.resume import Resume
from app.schemas.cover_letter_generation import CoverLetterGenerateRequest
from app.schemas.generated_artifact import (
    GeneratedArtifactCreate,
    GeneratedArtifactListItem,
    GeneratedArtifactRead,
    GeneratedArtifactUpdate,
)
from app.schemas.interview_prep_generation import InterviewPrepGenerateRequest
from app.services.cover_letter_service import generate_cover_letter
from app.services.interview_prep_service import generate_interview_prep

router = APIRouter(prefix="/api/v1/artifacts", tags=["artifacts"])


async def get_artifact_or_404(
    db: AsyncSession,
    artifact_id: int,
) -> GeneratedArtifact:
    # 统一处理不存在的产物记录，保持和现有模块相同的 404 风格。
    artifact = await db.get(GeneratedArtifact, artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Generated artifact not found")
    return artifact


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
) -> None:
    if resume_id is not None:
        resume = await db.get(Resume, resume_id)
        if resume is None:
            raise HTTPException(status_code=404, detail="Resume not found")

    if job_posting_id is not None:
        job = await db.get(JobPosting, job_posting_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job posting not found")

    if application_record_id is not None:
        application = await db.get(ApplicationRecord, application_record_id)
        if application is None:
            raise HTTPException(status_code=404, detail="Application record not found")


@router.post("", response_model=GeneratedArtifactRead, status_code=201)
async def create_artifact(
    payload: GeneratedArtifactCreate,
    db: AsyncSession = Depends(get_db),
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
    )

    artifact = GeneratedArtifact(**payload.model_dump())
    db.add(artifact)
    await db.commit()
    await db.refresh(artifact)
    return artifact


@router.get("", response_model=list[GeneratedArtifactListItem])
async def list_artifacts(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[GeneratedArtifact]:
    statement = (
        select(GeneratedArtifact)
        .order_by(GeneratedArtifact.created_at.desc())
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
) -> GeneratedArtifact:
    return await generate_cover_letter(db, payload)


@router.post(
    "/generate-interview-prep",
    response_model=GeneratedArtifactRead,
    status_code=201,
)
async def generate_interview_prep_artifact(
    payload: InterviewPrepGenerateRequest,
    db: AsyncSession = Depends(get_db),
) -> GeneratedArtifact:
    return await generate_interview_prep(db, payload)


@router.get("/{artifact_id}", response_model=GeneratedArtifactRead)
async def read_artifact(
    artifact_id: int,
    db: AsyncSession = Depends(get_db),
) -> GeneratedArtifact:
    return await get_artifact_or_404(db, artifact_id)


@router.patch("/{artifact_id}", response_model=GeneratedArtifactRead)
async def update_artifact(
    artifact_id: int,
    payload: GeneratedArtifactUpdate,
    db: AsyncSession = Depends(get_db),
) -> GeneratedArtifact:
    artifact = await get_artifact_or_404(db, artifact_id)
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
    )

    for field, value in update_data.items():
        setattr(artifact, field, value)

    await db.commit()
    await db.refresh(artifact)
    return artifact
