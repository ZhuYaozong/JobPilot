import hashlib
import re

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from sqlalchemy import select

from app.api.deps import CurrentUserDep, DbSession, ListLimit, ListOffset
from app.models.resume import Resume
from app.schemas.resume import ResumeCreate, ResumeListItem, ResumeRead, ResumeUpdate
from app.services.file_text_extractor import (
    FileExtractionError,
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
    file: UploadFile = File(..., description="PDF / DOCX / TXT / MD 简历文件"),
    title: str | None = Form(
        default=None,
        description="可选标题；不填时默认使用文件名主干。",
    ),
    auto_parse: bool = Form(
        default=True,
        description="为 true 时，文本抽取后立即运行 LLM 简历解析。",
    ),
) -> Resume:
    """接收简历文件，抽取文本，保存后按需立即解析。

    文件上传和手动粘贴最终都走同一个解析 service，保证两种入口的解析行为一致。
    """
    raw_bytes = await file.read()
    try:
        extracted = extract_text_from_upload(
            filename=file.filename or "upload",
            content_type=file.content_type,
            payload=raw_bytes,
        )
    except FileExtractionError as exc:
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
        # parse_resume 会原地更新 resume；如果 LLM 层抛 HTTPException，行会保留在
        # parse_status="pending"，前端详情页可以提示用户手动重试解析。
        try:
            resume = await parse_resume(db, resume)
        except HTTPException:
            # 解析失败要把错误返回给客户端，但不能删掉已上传的简历，方便用户稍后重试。
            await db.refresh(resume)
            raise

    return resume


def _derive_title_from_filename(filename: str) -> str:
    """``backend-resume-v3.pdf`` → ``backend-resume-v3``.

    如果文件名没有信息量，例如上传控件给出的 ``upload.pdf``，就回退到带时间戳的
    占位标题。处理前会先去掉路径和斜杠，避免浏览器传入奇怪的完整路径。
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
