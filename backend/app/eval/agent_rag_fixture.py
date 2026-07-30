"""Agent + RAG 正式评测使用的隔离知识库夹具。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.llm.embedding_client import EmbeddingClient
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.knowledge_document import KnowledgeDocument
from app.models.user import User
from app.services.knowledge_service import (
    create_knowledge_base,
    create_manual_document,
    delete_knowledge_base,
)


EVAL_USERNAME = "_agent_rag_eval_v1"
EVAL_KB_NAME = "agent-rag-eval-v1"
EVAL_KB_MARKER = "JobPilot Agent RAG Eval v1 — 仅供自动评测"


@dataclass(frozen=True, slots=True)
class DocumentSpec:
    """一份冻结评测文档及其数据库标题。"""

    source_document: str
    path: Path
    sha256: str


@dataclass(frozen=True, slots=True)
class FixtureSnapshot:
    """运行 Agent case 所需的稳定夹具标识与完整性信息。"""

    user_id: int
    username: str
    knowledge_base_id: int
    knowledge_base_name: str
    document_count: int
    chunk_count: int
    ready_document_count: int
    embedding_dimensions: int
    document_set_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_document_specs(
    config: dict[str, Any],
    *,
    config_path: Path,
) -> list[DocumentSpec]:
    """从 RAG 数据根目录加载 Markdown，并用评测集验证来源集合。"""
    dataset_root = _resolve_path(config_path, str(config["dataset_root"]))
    documents_dir = _resolve_path(config_path, str(config["documents_dir"]))
    evaluation_path = _resolve_path(config_path, str(config["evaluation_path"]))
    if not dataset_root.is_dir() or not documents_dir.is_dir():
        raise ValueError("RAG 数据根目录或 documents_dir 不存在")

    expected_sources = {
        str(row["source_document"])
        for row in _read_jsonl(evaluation_path)
    }
    specs: list[DocumentSpec] = []
    for path in sorted(documents_dir.glob("*.md")):
        resolved = path.resolve()
        try:
            source_document = resolved.relative_to(dataset_root).as_posix()
        except ValueError as exc:
            raise ValueError(f"文档越出 dataset_root: {resolved}") from exc
        specs.append(DocumentSpec(
            source_document=source_document,
            path=resolved,
            # create_manual_document 会先 strip；这里按实际入库正文冻结哈希。
            sha256=hashlib.sha256(
                resolved.read_text(encoding="utf-8").strip().encode("utf-8"),
            ).hexdigest(),
        ))

    expected_count = int(config.get("expected_document_count", 50))
    if len(specs) != expected_count:
        raise ValueError(f"评测文档应为 {expected_count} 份，实际 {len(specs)} 份")
    actual_sources = {spec.source_document for spec in specs}
    if actual_sources != expected_sources:
        missing = sorted(expected_sources - actual_sources)
        extra = sorted(actual_sources - expected_sources)
        raise ValueError(f"评测来源与文档集合不一致: missing={missing}, extra={extra}")
    return specs


async def prepare_fixture(
    config: dict[str, Any],
    *,
    config_path: Path,
    rebuild: bool,
) -> FixtureSnapshot:
    """创建或验证专用知识库；重建只触碰固定测试用户名下的评测库。"""
    specs = load_document_specs(config, config_path=config_path)
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    try:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            user = await _get_or_create_eval_user(db)
            bases = list((await db.execute(
                select(KnowledgeBase).where(
                    KnowledgeBase.user_id == user.id,
                    KnowledgeBase.name == EVAL_KB_NAME,
                ),
            )).scalars().all())
            for kb in bases:
                if kb.description != EVAL_KB_MARKER:
                    raise ValueError(
                        "发现同名但不带评测标记的知识库，拒绝自动修改",
                    )

            if rebuild:
                for kb in bases:
                    await delete_knowledge_base(db, kb)
                bases = []
            elif len(bases) > 1:
                raise ValueError("发现多个专用评测知识库，请使用 --rebuild-kb 清理")

            if bases:
                snapshot = await _snapshot(db, user, bases[0], specs)
                _assert_fixture_matches(snapshot, specs)
                return snapshot

            kb = await create_knowledge_base(
                db,
                user,
                name=EVAL_KB_NAME,
                description=EVAL_KB_MARKER,
                status="active",
            )
            embedding_client = EmbeddingClient()
            for position, spec in enumerate(specs, start=1):
                doc = await create_manual_document(
                    db,
                    kb=kb,
                    user=user,
                    title=spec.source_document,
                    body=spec.path.read_text(encoding="utf-8"),
                    source_url=spec.source_document,
                    embedding_client=embedding_client,
                    auto_index=True,
                )
                if doc.status != "ready":
                    raise RuntimeError(
                        f"文档索引失败 {spec.source_document}: {doc.error_detail}",
                    )
                print(
                    f"[知识库] {position}/{len(specs)} {spec.source_document} "
                    f"chunks={doc.chunk_count}",
                    flush=True,
                )
            snapshot = await _snapshot(db, user, kb, specs)
            _assert_fixture_matches(snapshot, specs)
            return snapshot
    finally:
        await engine.dispose()


async def load_fixture_snapshot(
    config: dict[str, Any],
    *,
    config_path: Path,
) -> FixtureSnapshot:
    """只读加载已准备夹具，正式运行前再次做完整性校验。"""
    specs = load_document_specs(config, config_path=config_path)
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    try:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            user = (await db.execute(
                select(User).where(User.username == EVAL_USERNAME),
            )).scalar_one_or_none()
            if user is None or not user.is_test_user:
                raise ValueError("专用评测用户不存在，请先使用 --prepare-kb")
            bases = list((await db.execute(
                select(KnowledgeBase).where(
                    KnowledgeBase.user_id == user.id,
                    KnowledgeBase.name == EVAL_KB_NAME,
                    KnowledgeBase.description == EVAL_KB_MARKER,
                ),
            )).scalars().all())
            if len(bases) != 1:
                raise ValueError("专用评测知识库数量不是1，请先使用 --rebuild-kb")
            snapshot = await _snapshot(db, user, bases[0], specs)
            _assert_fixture_matches(snapshot, specs)
            return snapshot
    finally:
        await engine.dispose()


async def _get_or_create_eval_user(db: AsyncSession) -> User:
    user = (await db.execute(
        select(User).where(User.username == EVAL_USERNAME),
    )).scalar_one_or_none()
    if user is not None:
        if not user.is_test_user:
            raise ValueError("固定评测用户名已被普通用户占用，拒绝继续")
        return user
    user = User(
        username=EVAL_USERNAME,
        display_name="Agent RAG Eval User",
        is_test_user=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _snapshot(
    db: AsyncSession,
    user: User,
    kb: KnowledgeBase,
    specs: list[DocumentSpec],
) -> FixtureSnapshot:
    documents = list((await db.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.user_id == user.id,
            KnowledgeDocument.knowledge_base_id == kb.id,
        ),
    )).scalars().all())
    expected_hashes = {spec.source_document: spec.sha256 for spec in specs}
    actual_hashes = {
        doc.title: hashlib.sha256(doc.raw_text.encode("utf-8")).hexdigest()
        for doc in documents
    }
    if actual_hashes != expected_hashes:
        raise ValueError("专用知识库文档标题或内容哈希已漂移，请使用 --rebuild-kb")
    chunk_count = int((await db.execute(
        select(func.count(KnowledgeChunk.id)).where(
            KnowledgeChunk.user_id == user.id,
            KnowledgeChunk.document_id.in_([doc.id for doc in documents]),
        ),
    )).scalar_one()) if documents else 0
    return FixtureSnapshot(
        user_id=user.id,
        username=user.username,
        knowledge_base_id=kb.id,
        knowledge_base_name=kb.name,
        document_count=len(documents),
        chunk_count=chunk_count,
        ready_document_count=sum(doc.status == "ready" for doc in documents),
        embedding_dimensions=int(settings.embedding_dimensions),
        document_set_sha256=_document_set_sha256(specs),
    )


def _assert_fixture_matches(
    snapshot: FixtureSnapshot,
    specs: list[DocumentSpec],
) -> None:
    if snapshot.document_count != len(specs):
        raise ValueError("专用知识库文档数不正确")
    if snapshot.ready_document_count != len(specs):
        raise ValueError("专用知识库存在未完成索引的文档")
    if snapshot.chunk_count <= 0:
        raise ValueError("专用知识库没有可检索 chunk")
    if snapshot.embedding_dimensions != 1024:
        raise ValueError(
            f"Embedding 维度应为1024，实际 {snapshot.embedding_dimensions}",
        )


def _document_set_sha256(specs: list[DocumentSpec]) -> str:
    payload = "\n".join(
        f"{spec.source_document}\t{spec.sha256}"
        for spec in sorted(specs, key=lambda item: item.source_document)
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _resolve_path(config_path: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    return path.resolve() if path.is_absolute() else (config_path.parent / path).resolve()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number} JSON无效") from exc
    return rows
