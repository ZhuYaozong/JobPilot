"""search_knowledge — Agent 的 RAG 检索工具。

这个工具负责把用户问题转成 query embedding，并在当前用户的
knowledge_chunks 里做 pgvector 相似度检索。它只读知识库，不写业务数据。

检索时会复用知识库索引阶段同一套独立 embedding 端点，将用户问题向量化，
再对当前用户的 chunks 做 top-K cosine distance 排序。工具结果会进入
``format_response``，由 LLM 基于召回内容生成回答。

权限边界必须始终按 ``user_id`` 过滤，即使 ``knowledge_base_id`` 为空也不能跨用户。
``knowledge_chunks.user_id`` 是专门为这个查询路径冗余的字段，避免每次检索都靠
多层 join 才能确认归属。

当前版本暂不做混合检索、rerank 和多知识库预筛选；如果后续 Recall@5 明显不足，
再引入 BM25+dense 或 reranker。
"""

from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.agent.tool_adapter import BaseTool, ToolContext, ToolSystemError
from app.llm.embedding_client import (
    EmbeddingClient,
    EmbeddingClientError,
    EmbeddingConfigError,
)
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.knowledge_document import KnowledgeDocument


# 限制单个命中的文本长度，避免一次检索把 format_response prompt 撑得过大。
# 单个 chunk 可能接近 800 字，top_k=5 时很容易把最终回复 prompt 撑到数千字。
# 这里在工具层先截断，简单稳定；如果未来要更高精度引用，再改成按句子边界裁剪。
MAX_CONTENT_PREVIEW_CHARS = 600


class SearchKnowledgeArgs(BaseModel):
    query: str = Field(
        min_length=1,
        max_length=500,
        description=(
            "用于检索当前用户知识库的自然语言问题或关键词短语。"
            "应该改写成更适合检索的表达，而不是机械复述用户原句。"
        ),
    )
    knowledge_base_id: int | None = Field(
        default=None,
        description=(
            "可选。将检索范围限制到单个 knowledge_base_id。"
            "为 null 时检索当前用户的全部知识库。"
        ),
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="最多返回的 chunk 数量，范围 1-20，默认 5。",
    )


class SearchKnowledgeTool(BaseTool):
    name = "search_knowledge"
    description = (
        "按语义相似度检索当前用户的知识库内容，例如公司背景、项目笔记、面试资料等。"
        "返回最多 top_k 个原文 chunk，并包含文档标题和 relevance 分数。"
        "当用户询问自己保存过的具体资料(例如“我在 ByteDance 做了什么项目”、"
        "“面试常被问的题目”、“这家公司的背景”)且答案不在对话历史中时使用。"
        "不要用它查询 resume/job/application 元数据；这些信息应使用 list_user_* 工具。"
    )
    args_schema = SearchKnowledgeArgs

    async def _execute(
        self,
        args: SearchKnowledgeArgs,
        ctx: ToolContext,
    ) -> dict[str, Any]:
        user_id = ctx.current_user.id

        if args.knowledge_base_id is not None:
            # 先校验 KB 归属，不能让用户通过显式 id 检索到别人的知识库。
            owned = await ctx.db.execute(
                select(KnowledgeBase.id).where(
                    KnowledgeBase.id == args.knowledge_base_id,
                    KnowledgeBase.user_id == user_id,
                ),
            )
            if owned.scalar_one_or_none() is None:
                return {
                    "ok": False,
                    "error_class": "knowledge_base_not_found",
                    "message_for_llm": (
                        f"知识库 #{args.knowledge_base_id} 不存在或不属于当前用户。"
                        "可以让用户确认知识库,或者去掉 knowledge_base_id 再试。"
                    ),
                    "user_facing_detail": "知识库不存在或无权访问。",
                }

        try:
            client = self._embedding_client()
            query_vectors = await client.embed([args.query])
        except EmbeddingConfigError as exc:
            # 配置缺失是用户/部署可修复的业务前置错误，不把 AgentRun 标 failed。
            return {
                "ok": False,
                "error_class": "embedding_config_missing",
                "message_for_llm": (
                    "知识库检索暂不可用,因为 embedding 接口没有配置。"
                    "请告知用户先在系统设置里补 EMBEDDING_* 环境变量。"
                ),
                "user_facing_detail": str(exc),
            }
        except EmbeddingClientError as exc:
            # 远端不可用或响应坏掉属于系统错误，模型重试同一参数没有帮助。
            # 这里升级为 ToolSystemError，让 workflow 把 AgentRun 标记为 failed。
            raise ToolSystemError(
                self.name, "embedding_unavailable", str(exc),
            ) from exc

        if not query_vectors:
            # 正常 embedding client 不应返回空向量；保留这个分支防御兼容服务异常。
            return {
                "ok": False,
                "error_class": "empty_query_embedding",
                "message_for_llm": "查询向量为空,无法检索。请改写问题后重试。",
                "user_facing_detail": "embedding API returned no vectors",
            }
        query_vec = query_vectors[0]

        # cosine distance 越小越相关；按 user_id 过滤是最核心的 ACL 约束。
        # ``embedding <=> :vec`` 会命中 pgvector 的 HNSW 索引；同时过滤空 embedding，
        # 避免把 pending / failed 文档的旧行暴露给 Agent。
        distance_expr = KnowledgeChunk.embedding.cosine_distance(query_vec)
        stmt = (
            select(
                KnowledgeChunk.id,
                KnowledgeChunk.document_id,
                KnowledgeChunk.chunk_index,
                KnowledgeChunk.content,
                KnowledgeChunk.char_start,
                KnowledgeChunk.char_end,
                KnowledgeDocument.title,
                KnowledgeDocument.knowledge_base_id,
                KnowledgeDocument.source_type,
                distance_expr.label("distance"),
            )
            .join(
                KnowledgeDocument,
                KnowledgeChunk.document_id == KnowledgeDocument.id,
            )
            .where(
                KnowledgeChunk.user_id == user_id,
                KnowledgeChunk.embedding.is_not(None),
            )
        )
        if args.knowledge_base_id is not None:
            # 如果 UI/模型指定了知识库，进一步收窄到该 KB；workflow 也会强制覆盖 UI 选择。
            stmt = stmt.where(
                KnowledgeDocument.knowledge_base_id == args.knowledge_base_id,
            )
        stmt = stmt.order_by(distance_expr).limit(args.top_k)

        rows = (await ctx.db.execute(stmt)).all()

        # 把 distance 同时映射成 relevance，方便模型用更直观的 0-1 分数判断可信度。
        hits = [
            {
                "chunk_id": row.id,
                "document_id": row.document_id,
                "document_title": row.title,
                "knowledge_base_id": row.knowledge_base_id,
                "source_type": row.source_type,
                "chunk_index": row.chunk_index,
                "char_start": row.char_start,
                "char_end": row.char_end,
                "content": _trim(row.content, MAX_CONTENT_PREVIEW_CHARS),
                "distance": float(row.distance),
                # 把 cosine distance 的 [0, 2] 区间映射成 [0, 1] relevance，
                # 模型读起来比“距离越小越好”更直观。
                "relevance": max(0.0, 1.0 - float(row.distance) / 2.0),
            }
            for row in rows
        ]

        return {
            "ok": True,
            "data": {
                "query": args.query,
                "knowledge_base_id": args.knowledge_base_id,
                "hits": hits,
                "count": len(hits),
            },
        }

    def _embedding_client(self) -> EmbeddingClient:
        """测试替换 embedding client 的钩子。

        默认每次调用创建一个新 client。httpx client 本身很轻，而且这种写法让测试
        可以通过覆写方法精确替换 embedding 行为。
        """
        return EmbeddingClient()


def _trim(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    # 优先在空白处截断，减少给模型看的片段出现半个英文词或半段标记。
    # 如果找不到合适空白，就直接硬截断；中文文本没有空格时这种退路很常见。
    cut = text[:max_chars]
    last_space = cut.rfind(" ")
    if last_space > max_chars - 80:
        cut = cut[:last_space]
    return cut + "…"
