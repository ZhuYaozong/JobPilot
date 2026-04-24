from collections.abc import Callable
import hashlib

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application_record import ApplicationRecord
from app.models.generated_artifact import GeneratedArtifact
from app.models.job_posting import JobPosting
from app.models.match_result import MatchResult
from app.models.resume import Resume
from app.models.user import User

DEFAULT_DEMO_USERNAME = "demo"
DEFAULT_SANDBOX_USERNAME = "sandbox"
DEFAULT_TEST_USERNAME = "test"

_DEV_USER_PRESETS: dict[str, tuple[str, bool]] = {
    DEFAULT_DEMO_USERNAME: ("Demo User", False),
    DEFAULT_SANDBOX_USERNAME: ("Sandbox User", False),
    DEFAULT_TEST_USERNAME: ("Pytest User", True),
}

MAX_USERNAME_LENGTH = 64
MAX_DISPLAY_NAME_LENGTH = 255


def normalize_username(requested_username: str | None) -> str:
    normalized = (requested_username or DEFAULT_DEMO_USERNAME).strip().lower()
    normalized = normalized or DEFAULT_DEMO_USERNAME
    if len(normalized) <= MAX_USERNAME_LENGTH:
        return normalized

    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12]
    prefix = normalized[: MAX_USERNAME_LENGTH - len(digest) - 1]
    return f"{prefix}-{digest}"


def build_user_defaults(username: str) -> dict[str, object]:
    preset = _DEV_USER_PRESETS.get(username)
    if preset is not None:
        display_name, is_test_user = preset
        return {
            "username": username,
            "display_name": display_name,
            "is_test_user": is_test_user,
        }

    display_name = username.replace("-", " ").replace("_", " ").title()
    return {
        "username": username,
        "display_name": (display_name or f"User {username}")[:MAX_DISPLAY_NAME_LENGTH],
        "is_test_user": False,
    }


async def get_or_create_user_by_username(
    db: AsyncSession,
    requested_username: str | None,
) -> User:
    username = normalize_username(requested_username)
    statement = select(User).where(User.username == username)
    result = await db.execute(statement)
    user = result.scalar_one_or_none()
    if user is not None:
        return user

    user = User(**build_user_defaults(username))
    db.add(user)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        retry_result = await db.execute(statement)
        existing_user = retry_result.scalar_one_or_none()
        if existing_user is None:
            raise
        return existing_user

    await db.refresh(user)
    return user


async def _get_owned_record_or_404[T](
    db: AsyncSession,
    statement_builder: Callable[[], object],
    detail: str,
) -> T:
    result = await db.execute(statement_builder())
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail=detail)
    return record


async def get_resume_for_user_or_404(
    db: AsyncSession,
    resume_id: int,
    current_user: User,
) -> Resume:
    return await _get_owned_record_or_404(
        db,
        lambda: select(Resume).where(
            Resume.id == resume_id,
            Resume.user_id == current_user.id,
        ),
        detail="Resume not found",
    )


async def get_job_posting_for_user_or_404(
    db: AsyncSession,
    job_id: int,
    current_user: User,
) -> JobPosting:
    return await _get_owned_record_or_404(
        db,
        lambda: select(JobPosting).where(
            JobPosting.id == job_id,
            JobPosting.user_id == current_user.id,
        ),
        detail="Job posting not found",
    )


async def get_match_result_for_user_or_404(
    db: AsyncSession,
    match_id: int,
    current_user: User,
) -> MatchResult:
    return await _get_owned_record_or_404(
        db,
        lambda: select(MatchResult).where(
            MatchResult.id == match_id,
            MatchResult.user_id == current_user.id,
        ),
        detail="Match result not found",
    )


async def get_generated_artifact_for_user_or_404(
    db: AsyncSession,
    artifact_id: int,
    current_user: User,
) -> GeneratedArtifact:
    return await _get_owned_record_or_404(
        db,
        lambda: select(GeneratedArtifact).where(
            GeneratedArtifact.id == artifact_id,
            GeneratedArtifact.user_id == current_user.id,
        ),
        detail="Generated artifact not found",
    )


async def get_application_record_for_user_or_404(
    db: AsyncSession,
    application_id: int,
    current_user: User,
) -> ApplicationRecord:
    return await _get_owned_record_or_404(
        db,
        lambda: select(ApplicationRecord).where(
            ApplicationRecord.id == application_id,
            ApplicationRecord.user_id == current_user.id,
        ),
        detail="Application record not found",
    )


async def ensure_resume_and_job_exist_for_user(
    db: AsyncSession,
    resume_id: int,
    job_posting_id: int,
    current_user: User,
) -> tuple[Resume, JobPosting]:
    resume = await get_resume_for_user_or_404(db, resume_id, current_user)
    job = await get_job_posting_for_user_or_404(db, job_posting_id, current_user)
    return resume, job


async def get_latest_match_result_for_user(
    db: AsyncSession,
    current_user: User,
    resume_id: int,
    job_posting_id: int,
) -> MatchResult | None:
    statement = (
        select(MatchResult)
        .where(
            MatchResult.user_id == current_user.id,
            MatchResult.resume_id == resume_id,
            MatchResult.job_posting_id == job_posting_id,
        )
        .order_by(MatchResult.created_at.desc(), MatchResult.id.desc())
        .limit(1)
    )
    result = await db.execute(statement)
    return result.scalar_one_or_none()
