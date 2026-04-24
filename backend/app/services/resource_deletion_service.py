from collections.abc import Sequence

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application_event import ApplicationEvent
from app.models.application_record import ApplicationRecord
from app.models.artifact_feedback_event import ArtifactFeedbackEvent
from app.models.generated_artifact import GeneratedArtifact
from app.models.job_posting import JobPosting
from app.models.match_result import MatchResult
from app.models.resume import Resume
from app.models.resume_version import ResumeVersion
from app.models.user import User


async def _fetch_ids(db: AsyncSession, statement) -> list[int]:
    result = await db.execute(statement)
    return [int(item) for item in result.scalars().all()]


async def _delete_artifact_feedback(
    db: AsyncSession,
    artifact_ids: Sequence[int],
) -> None:
    if not artifact_ids:
        return

    await db.execute(
        delete(ArtifactFeedbackEvent).where(
            ArtifactFeedbackEvent.generated_artifact_id.in_(artifact_ids),
        ),
    )


async def _delete_artifacts(db: AsyncSession, artifact_ids: Sequence[int]) -> None:
    if not artifact_ids:
        return

    await _delete_artifact_feedback(db, artifact_ids)
    await db.execute(
        delete(GeneratedArtifact).where(GeneratedArtifact.id.in_(artifact_ids)),
    )


async def _delete_application_events(
    db: AsyncSession,
    application_ids: Sequence[int],
) -> None:
    if not application_ids:
        return

    await db.execute(
        delete(ApplicationEvent).where(
            ApplicationEvent.application_record_id.in_(application_ids),
        ),
    )


async def _delete_applications(
    db: AsyncSession,
    application_ids: Sequence[int],
) -> None:
    if not application_ids:
        return

    await _delete_application_events(db, application_ids)
    await db.execute(
        delete(ApplicationRecord).where(ApplicationRecord.id.in_(application_ids)),
    )


async def delete_application_record_tree(
    db: AsyncSession,
    application: ApplicationRecord,
    current_user: User,
) -> None:
    artifact_ids = await _fetch_ids(
        db,
        select(GeneratedArtifact.id).where(
            GeneratedArtifact.user_id == current_user.id,
            GeneratedArtifact.application_record_id == application.id,
        ),
    )
    await _delete_artifacts(db, artifact_ids)
    await _delete_application_events(db, [application.id])
    await db.delete(application)
    await db.commit()


async def delete_match_result_tree(
    db: AsyncSession,
    match: MatchResult,
) -> None:
    await db.delete(match)
    await db.commit()


async def delete_resume_tree(
    db: AsyncSession,
    resume: Resume,
    current_user: User,
) -> None:
    application_ids = await _fetch_ids(
        db,
        select(ApplicationRecord.id).where(
            ApplicationRecord.user_id == current_user.id,
            ApplicationRecord.resume_id == resume.id,
        ),
    )

    artifact_links = [GeneratedArtifact.resume_id == resume.id]
    if application_ids:
        artifact_links.append(GeneratedArtifact.application_record_id.in_(application_ids))

    artifact_ids = await _fetch_ids(
        db,
        select(GeneratedArtifact.id).where(
            GeneratedArtifact.user_id == current_user.id,
            or_(*artifact_links),
        ),
    )

    await _delete_artifacts(db, artifact_ids)
    await _delete_applications(db, application_ids)
    await db.execute(
        delete(ResumeVersion).where(ResumeVersion.resume_id == resume.id),
    )
    await db.execute(
        delete(MatchResult).where(
            MatchResult.user_id == current_user.id,
            MatchResult.resume_id == resume.id,
        ),
    )
    await db.delete(resume)
    await db.commit()


async def delete_job_posting_tree(
    db: AsyncSession,
    job: JobPosting,
    current_user: User,
) -> None:
    application_ids = await _fetch_ids(
        db,
        select(ApplicationRecord.id).where(
            ApplicationRecord.user_id == current_user.id,
            ApplicationRecord.job_posting_id == job.id,
        ),
    )

    artifact_links = [GeneratedArtifact.job_posting_id == job.id]
    if application_ids:
        artifact_links.append(GeneratedArtifact.application_record_id.in_(application_ids))

    artifact_ids = await _fetch_ids(
        db,
        select(GeneratedArtifact.id).where(
            GeneratedArtifact.user_id == current_user.id,
            or_(*artifact_links),
        ),
    )

    await _delete_artifacts(db, artifact_ids)
    await _delete_applications(db, application_ids)
    await db.execute(
        delete(ResumeVersion).where(ResumeVersion.job_posting_id == job.id),
    )
    await db.execute(
        delete(MatchResult).where(
            MatchResult.user_id == current_user.id,
            MatchResult.job_posting_id == job.id,
        ),
    )
    await db.delete(job)
    await db.commit()
