"""把一段文本作为新文档存入指定知识库(并同步索引)。

# 重要触发约束
本工具**只在用户明确要求保存时调用**。用户只是粘贴公司背景、面试笔记、项目描述、
或在对话里一边聊一边给背景信息时,**不要**自动调用 — Agent 应当直接 respond_directly
回应内容本身。
触发关键词例:"保存到知识库""帮我记到知识库""把这段加到 X 知识库""存到我的知识库"。
如果用户表达了保存意图但没指定 knowledge_base_id,Agent 应先 respond_directly 询问
要存到哪个库,**不要猜测**一个 id。

# 链路
复用 ``knowledge_service.create_manual_document``,它会:
1) 校验 KB 归属当前用户
2) 写入 KnowledgeDocument(source_type='manual')
3) **同步**执行切片 + embedding(可能耗时几秒)

# 错误契约
- KB 不存在 → 业务错 knowledge_base_not_found
- content 太短(< 30 字)→ 业务错 content_too_short
- 索引失败不会抛(service 把状态写到 status=failed),工具仍返回 ok=True
  并把 document.status 暴露给 LLM,让 LLM 转述给用户
"""

from typing import Any

from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.agent.tool_adapter import BaseTool, ToolContext
from app.services.knowledge_service import (
    create_manual_document,
    get_knowledge_base_for_user_or_404,
)


_BUSINESS_DETAIL_TO_ERROR_CLASS: dict[str, str] = {
    "Knowledge base not found": "knowledge_base_not_found",
}

_BUSINESS_LLM_MESSAGES: dict[str, str] = {
    "knowledge_base_not_found": (
        "指定的知识库不存在;请让用户确认 knowledge_base_id,或在 Assistant 上下文里选一个知识库。"
    ),
    "content_too_short": (
        "正文太短(少于 30 字),无法作为知识库文档保存;请让用户补充更多内容后重试。"
    ),
}


class AddKnowledgeTextToolArgs(BaseModel):
    knowledge_base_id: int = Field(
        ...,
        description=(
            "要保存到的知识库 id。**不要猜测**;如果用户没指定且本轮上下文也没选中知识库,"
            "先 respond_directly 询问用户。"
        ),
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="知识库文档标题,例如『腾讯 AI 应用工程师面试反馈 2026-05』。",
    )
    content: str = Field(
        ...,
        min_length=30,
        description="文档正文,至少 30 字;太短的内容会被 service 拒绝。",
    )


class AddKnowledgeTextTool(BaseTool):
    name = "add_knowledge_text"
    description = (
        "把一段文本作为新文档保存到指定知识库,并立即索引(同步切片 + embedding)。"
        "**仅在用户明确要求保存时才调用**(关键词如『保存到知识库』『帮我记到知识库』"
        "『把这段加到 X 知识库』『存到我的知识库』)。"
        "用户只是粘贴公司背景、面试笔记、项目描述、或一边聊一边给背景信息时,"
        "**不要**自动调用本工具 — 直接用 respond_directly 回应即可。"
        "如果用户表达了保存意图但没指定 knowledge_base_id,先 respond_directly "
        "询问要存到哪个知识库,**绝不**自己猜测一个 id。"
    )
    args_schema = AddKnowledgeTextToolArgs

    async def _execute(
        self,
        args: AddKnowledgeTextToolArgs,
        ctx: ToolContext,
    ) -> dict[str, Any]:
        # 先校验 KB 归属,业务错走 ok=false,不让 service 内部 raise 散在多处。
        try:
            kb = await get_knowledge_base_for_user_or_404(
                ctx.db,
                args.knowledge_base_id,
                ctx.current_user,
            )
        except HTTPException as exc:
            return self._http_exception_to_result(exc)

        try:
            doc = await create_manual_document(
                ctx.db,
                kb=kb,
                user=ctx.current_user,
                title=args.title,
                body=args.content,
                source_url=None,
                # embedding_client=None → 走 EmbeddingClient 默认实例
            )
        except HTTPException as exc:
            # 已知的只有 400「正文太短」。schema 层 min_length=30 已挡住,这里是双保险。
            if exc.status_code == 400:
                return {
                    "ok": False,
                    "error_class": "content_too_short",
                    "message_for_llm": _BUSINESS_LLM_MESSAGES["content_too_short"],
                    "user_facing_detail": (
                        exc.detail if isinstance(exc.detail, str) else str(exc.detail)
                    ),
                }
            return self._http_exception_to_result(exc)

        # 索引可能失败(EmbeddingConfigError / EmbeddingClientError),service 已把
        # status 设成 failed 并存了 error_detail。这里把状态透出给 LLM,让回复能转述。
        return {
            "ok": True,
            "data": {
                "document_id": doc.id,
                "knowledge_base_id": doc.knowledge_base_id,
                "title": doc.title,
                "status": doc.status,
                "chunk_count": doc.chunk_count,
                "error_detail": doc.error_detail,
            },
        }

    def _http_exception_to_result(self, exc: HTTPException) -> dict[str, Any]:
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        error_class = _BUSINESS_DETAIL_TO_ERROR_CLASS.get(detail, "unknown_business_error")
        return {
            "ok": False,
            "error_class": error_class,
            "message_for_llm": _BUSINESS_LLM_MESSAGES.get(error_class, detail),
            "user_facing_detail": detail,
        }
