"""知识库与文档的 HTTP API 层。

当前有两组资源路径：
- /api/v1/knowledge/bases                → 知识库 CRUD
- /api/v1/knowledge/bases/{id}/documents → 某个知识库下的文档 CRUD

索引相关接口在 7'c2/7'c3 增量加入：重新索引、chunk 预览和 Agent 检索工具。
"""

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel

from app.api.deps import CurrentUserDep, DbSession, ListLimit, ListOffset
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_document import KnowledgeDocument
from app.schemas.knowledge import (
    KnowledgeChunkPreview,
    KnowledgeBaseCreate,
    KnowledgeBaseListItem,
    KnowledgeBaseRead,
    KnowledgeBaseUpdate,
    KnowledgeDocumentListItem,
    KnowledgeDocumentRead,
)
from app.services import knowledge_service

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


# ---------- 知识库 --------------------------------------------------------


def _to_kb_list_item(
    kb: KnowledgeBase, document_count: int,
) -> KnowledgeBaseListItem:
    """手工构造列表 DTO，而不是完全依赖 ``from_attributes``。

    ``document_count`` 不是 KnowledgeBase 表字段，而是 service 层 join/count 算出来的。
    显式构造可以避免未来 ORM 重构时误以为该字段会自动从模型上读到。
    """
    return KnowledgeBaseListItem(
        id=kb.id,
        name=kb.name,
        description=kb.description,
        status=kb.status,
        document_count=document_count,
        created_at=kb.created_at,
        updated_at=kb.updated_at,
    )


@router.get("/bases", response_model=list[KnowledgeBaseListItem])
async def list_knowledge_bases(
    db: DbSession,
    current_user: CurrentUserDep,
    limit: ListLimit = 50,
    offset: ListOffset = 0,
    include_archived: bool = False,
) -> list[KnowledgeBaseListItem]:
    pairs = await knowledge_service.list_knowledge_bases(
        db,
        current_user,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )
    return [_to_kb_list_item(kb, count) for kb, count in pairs]


@router.post(
    "/bases", response_model=KnowledgeBaseRead, status_code=201,
)
async def create_knowledge_base(
    payload: KnowledgeBaseCreate,
    db: DbSession,
    current_user: CurrentUserDep,
) -> KnowledgeBaseRead:
    kb = await knowledge_service.create_knowledge_base(
        db,
        current_user,
        name=payload.name,
        description=payload.description,
        status=payload.status,
    )
    return _to_kb_list_item(kb, 0)


@router.get("/bases/{kb_id}", response_model=KnowledgeBaseRead)
async def read_knowledge_base(
    kb_id: int,
    db: DbSession,
    current_user: CurrentUserDep,
) -> KnowledgeBaseRead:
    kb = await knowledge_service.get_knowledge_base_for_user_or_404(
        db, kb_id, current_user,
    )
    count = await knowledge_service.count_documents_in(
        db, kb_id, current_user.id,
    )
    return _to_kb_list_item(kb, count)


@router.patch("/bases/{kb_id}", response_model=KnowledgeBaseRead)
async def update_knowledge_base(
    kb_id: int,
    payload: KnowledgeBaseUpdate,
    db: DbSession,
    current_user: CurrentUserDep,
) -> KnowledgeBaseRead:
    kb = await knowledge_service.get_knowledge_base_for_user_or_404(
        db, kb_id, current_user,
    )
    kb = await knowledge_service.update_knowledge_base(
        db,
        kb,
        name=payload.name,
        description=payload.description,
        status=payload.status,
    )
    count = await knowledge_service.count_documents_in(
        db, kb_id, current_user.id,
    )
    return _to_kb_list_item(kb, count)


@router.delete("/bases/{kb_id}", status_code=204)
async def delete_knowledge_base(
    kb_id: int,
    db: DbSession,
    current_user: CurrentUserDep,
) -> Response:
    kb = await knowledge_service.get_knowledge_base_for_user_or_404(
        db, kb_id, current_user,
    )
    await knowledge_service.delete_knowledge_base(db, kb)
    return Response(status_code=204)


# ---------- 文档 ----------------------------------------------------------


def _to_doc_list_item(doc: KnowledgeDocument) -> KnowledgeDocumentListItem:
    return KnowledgeDocumentListItem(
        id=doc.id,
        knowledge_base_id=doc.knowledge_base_id,
        title=doc.title,
        source_type=doc.source_type,
        source_url=doc.source_url,
        chunk_count=doc.chunk_count,
        status=doc.status,
        error_detail=doc.error_detail,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@router.get(
    "/bases/{kb_id}/documents",
    response_model=list[KnowledgeDocumentListItem],
)
async def list_documents(
    kb_id: int,
    db: DbSession,
    current_user: CurrentUserDep,
    limit: ListLimit = 50,
    offset: ListOffset = 0,
) -> list[KnowledgeDocumentListItem]:
    # 先校验知识库归属；文档列表和直接读取知识库必须遵守同一条 ACL 规则。
    await knowledge_service.get_knowledge_base_for_user_or_404(
        db, kb_id, current_user,
    )
    docs = await knowledge_service.list_documents(
        db, kb_id, current_user, limit=limit, offset=offset,
    )
    return [_to_doc_list_item(doc) for doc in docs]


@router.post(
    "/bases/{kb_id}/documents/upload",
    response_model=KnowledgeDocumentRead,
    status_code=201,
)
async def upload_document(
    kb_id: int,
    db: DbSession,
    current_user: CurrentUserDep,
    file: UploadFile = File(..., description="PDF / DOCX / TXT / MD"),
    title: str | None = Form(default=None),
) -> KnowledgeDocumentRead:
    kb = await knowledge_service.get_knowledge_base_for_user_or_404(
        db, kb_id, current_user,
    )
    raw_bytes = await file.read()
    doc = await knowledge_service.upload_document(
        db,
        kb=kb,
        user=current_user,
        filename=file.filename or "upload",
        content_type=file.content_type,
        payload=raw_bytes,
        title_override=title,
    )
    return _to_doc_full(doc)


class _ManualDocumentBody(BaseModel):
    """粘贴文本建档接口专用 schema。

    只有这个 endpoint 需要它，放在本文件内能减少全局 schema 模块的噪声。
    """

    title: str
    body: str
    source_url: str | None = None


@router.post(
    "/bases/{kb_id}/documents",
    response_model=KnowledgeDocumentRead,
    status_code=201,
)
async def create_manual_document(
    kb_id: int,
    payload: _ManualDocumentBody,
    db: DbSession,
    current_user: CurrentUserDep,
) -> KnowledgeDocumentRead:
    kb = await knowledge_service.get_knowledge_base_for_user_or_404(
        db, kb_id, current_user,
    )
    doc = await knowledge_service.create_manual_document(
        db,
        kb=kb,
        user=current_user,
        title=payload.title,
        body=payload.body,
        source_url=payload.source_url,
    )
    return _to_doc_full(doc)


@router.get(
    "/documents/{document_id}", response_model=KnowledgeDocumentRead,
)
async def read_document(
    document_id: int,
    db: DbSession,
    current_user: CurrentUserDep,
) -> KnowledgeDocumentRead:
    doc = await knowledge_service.get_document_for_user_or_404(
        db, document_id, current_user,
    )
    return _to_doc_full(doc)


@router.get(
    "/documents/{document_id}/chunks",
    response_model=list[KnowledgeChunkPreview],
)
async def list_document_chunks(
    document_id: int,
    db: DbSession,
    current_user: CurrentUserDep,
    limit: ListLimit = 50,
    offset: ListOffset = 0,
) -> list[KnowledgeChunkPreview]:
    doc = await knowledge_service.get_document_for_user_or_404(
        db, document_id, current_user,
    )
    chunks = await knowledge_service.list_document_chunks(
        db, doc, limit=limit, offset=offset,
    )
    return [KnowledgeChunkPreview.model_validate(chunk) for chunk in chunks]


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(
    document_id: int,
    db: DbSession,
    current_user: CurrentUserDep,
) -> Response:
    doc = await knowledge_service.get_document_for_user_or_404(
        db, document_id, current_user,
    )
    await knowledge_service.delete_document(db, doc)
    return Response(status_code=204)


@router.post(
    "/documents/{document_id}/reindex", response_model=KnowledgeDocumentRead,
)
async def reindex_document(
    document_id: int,
    db: DbSession,
    current_user: CurrentUserDep,
) -> KnowledgeDocumentRead:
    """对文档重新执行切片和 embedding。

    常见场景是上一次因为 embedding 配置缺失或供应商失败落到 ``status=failed``。
    用户修复配置后调用这里，会删除旧 chunks 并从头索引。索引仍在请求内同步执行；
    状态机细节见 :mod:`knowledge_indexing_service`。
    """
    doc = await knowledge_service.get_document_for_user_or_404(
        db, document_id, current_user,
    )
    doc = await knowledge_service.reindex_document(db, doc)
    return _to_doc_full(doc)


def _to_doc_full(doc: KnowledgeDocument) -> KnowledgeDocumentRead:
    return KnowledgeDocumentRead(
        id=doc.id,
        knowledge_base_id=doc.knowledge_base_id,
        title=doc.title,
        source_type=doc.source_type,
        source_url=doc.source_url,
        chunk_count=doc.chunk_count,
        status=doc.status,
        error_detail=doc.error_detail,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        raw_text=doc.raw_text,
        extra_metadata=doc.extra_metadata,
    )
