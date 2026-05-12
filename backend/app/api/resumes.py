import hashlib
import re

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from sqlalchemy import select

from app.api.deps import CurrentUserDep, DbSession, ListLimit, ListOffset
from app.models.resume import Resume
from app.schemas.resume import ResumeCreate, ResumeListItem, ResumeRead, ResumeUpdate
from app.services.resume_file_extractor import (
    ResumeExtractionError,
    extract_text_from_upload,
)
from app.services.resume_parsing_service import parse_resume
from app.services.resource_deletion_service import delete_resume_tree
from app.services.user_scope_service import get_resume_for_user_or_404

router = APIRouter(prefix="/api/v1/resumes", tags=["resumes"])


@router.post("", response_model=ResumeRead, status_code=201)
async def create_resume(
    payload: ResumeCreate,
    db: DbSession,
    current_user: CurrentUserDep,
) -> Resume:
    resume = Resume(user_id=current_user.id, **payload.model_dump())
    db.add(resume)
    await db.commit()
    await db.refresh(resume)
    return resume


@router.post("/upload", response_model=ResumeRead, status_code=201)
async def upload_resume(
    db: DbSession,
    current_user: CurrentUserDep,
    file: UploadFile = File(..., description="PDF / DOCX / TXT / MD resume"),
    title: str | None = Form(
        default=None,
        description="Override title; defaults to the filename stem.",
    ),
    auto_parse: bool = Form(
        default=True,
        description="If true (default), run LLM parsing immediately after extraction.",
    ),
) -> Resume:
    """Accept a file upload, extract text, persist + (optionally) parse.

    The extracted text drives the same downstream pipeline that the manual
    "paste raw text" flow uses — we share the parsing service so behaviour
    stays consistent across both entry points.
    """
    raw_bytes = await file.read()
    try:
        extracted = extract_text_from_upload(
            filename=file.filename or "upload",
            content_type=file.content_type,
            payload=raw_bytes,
        )
    except ResumeExtractionError as exc:
        raise HTTPException(status_code=400, detail=exc.user_message) from exc

    derived_title = (title or _derive_title_from_filename(file.filename or ""))
    content_hash = hashlib.sha256(extracted.text.encode("utf-8")).hexdigest()

    resume = Resume(
        user_id=current_user.id,
        title=derived_title,
        raw_text=extracted.text,
        content_hash=content_hash,
        source_type=extracted.source_type,
        parse_status="pending",
    )
    db.add(resume)
    await db.commit()
    await db.refresh(resume)

    if auto_parse:
        # parse_resume mutates the resume in place; HTTPException from the
        # LLM layer leaves the row at parse_status="pending" which the UI
        # can flag for a manual retry from the detail page.
        try:
            resume = await parse_resume(db, resume)
        except HTTPException:
            # Surface the parsing failure code to the client but keep the
            # resume row — they can retry parse_resume_detail from the UI.
            await db.refresh(resume)
            raise

    return resume


def _derive_title_from_filename(filename: str) -> str:
    """``backend-resume-v3.pdf`` → ``backend-resume-v3``.

    Falls back to a date-stamped placeholder when the filename is unhelpful
    (e.g. ``upload.pdf`` from the upload widget's anonymous mode). Anything
    weird in the name (paths, slashes) is stripped first.
    """
    sanitised = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
    stem = re.sub(r"\.[^.]+$", "", sanitised).strip()
    if stem and stem.lower() not in {"upload", "resume", "untitled"}:
        return stem[:255]
    from datetime import datetime
    return f"上传简历 {datetime.now().strftime('%Y-%m-%d %H:%M')}"


@router.get("", response_model=list[ResumeListItem])
async def list_resumes(
    db: DbSession,
    current_user: CurrentUserDep,
    limit: ListLimit = 20,
    offset: ListOffset = 0,
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
    db: DbSession,
    current_user: CurrentUserDep,
) -> Resume:
    return await get_resume_for_user_or_404(db, resume_id, current_user)


@router.post("/{resume_id}/parse", response_model=ResumeRead)
async def parse_resume_detail(
    resume_id: int,
    db: DbSession,
    current_user: CurrentUserDep,
) -> Resume:
    resume = await get_resume_for_user_or_404(db, resume_id, current_user)
    return await parse_resume(db, resume)


@router.patch("/{resume_id}", response_model=ResumeRead)
async def update_resume(
    resume_id: int,
    payload: ResumeUpdate,
    db: DbSession,
    current_user: CurrentUserDep,
) -> Resume:
    resume = await get_resume_for_user_or_404(db, resume_id, current_user)
    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(resume, field, value)

    await db.commit()
    await db.refresh(resume)
    return resume


@router.delete("/{resume_id}", status_code=204)
async def delete_resume(
    resume_id: int,
    db: DbSession,
    current_user: CurrentUserDep,
) -> None:
    resume = await get_resume_for_user_or_404(db, resume_id, current_user)
    await delete_resume_tree(db, resume, current_user)
