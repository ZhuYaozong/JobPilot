"""search_knowledge — Agent 的 RAG 检索工具。

中文说明：这个工具负责把用户问题转成 query embedding，并在当前用户的
knowledge_chunks 里做 pgvector 相似度检索。它只读知识库，不写业务数据。

Embeds the user's natural-language query through the same independent
embedding endpoint that indexed the knowledge documents, then runs a
top-K cosine-distance search against the user's chunks. The agent then
passes the results into ``format_response`` so the LLM can synthesise an
answer grounded in retrieved content.

ACL invariant: every search is scoped by ``user_id`` (never cross-user),
even when ``knowledge_base_id`` is null. The user_id column on chunks is
denormalised exactly for this query path.

Out of scope for this slice:
- Hybrid (BM25 + dense) retrieval — dense-only for v1
- Reranking — bring this in if Recall@5 drops below ~70%
- Multi-KB shortlisting — caller passes a specific knowledge_base_id or
  nothing
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


# 中文说明：限制单个命中的文本长度，避免一次检索把 format_response prompt 撑得过大。
# How many chars of each hit to surface to the agent. Full chunk content
# can be ~800 chars; with 5 hits that's 4000 chars in the format_response
# prompt — fine but not free, and the agent rarely needs everything.
# Trimming on the LLM side would be more accurate but more brittle.
MAX_CONTENT_PREVIEW_CHARS = 600


class SearchKnowledgeArgs(BaseModel):
    query: str = Field(
        min_length=1,
        max_length=500,
        description=(
            "Natural-language question or keyword phrase to search the user's"
            " knowledge base. Should be the most retrieval-friendly form of"
            " what the user asked, not a literal echo of the user's message."
        ),
    )
    knowledge_base_id: int | None = Field(
        default=None,
        description=(
            "Optional. Narrow the search to a single knowledge base. Leave"
            " null to search across all of the user's knowledge bases."
        ),
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of chunks to return (1-20, default 5).",
    )


class SearchKnowledgeTool(BaseTool):
    name = "search_knowledge"
    description = (
        "Search the user's knowledge base (company background, project notes,"
        " interview prep, etc.) by semantic similarity. Returns up to top_k"
        " chunks of original text with their document title and a relevance"
        " score. Use this when the user asks about specific content they"
        " saved (e.g. '我在 ByteDance 做了什么项目', '面试常被问的题目',"
        " '这家公司的背景') and the answer isn't already in conversation"
        " history. NOT for resume/job/application metadata — those have"
        " dedicated list_user_* tools."
    )
    args_schema = SearchKnowledgeArgs

    async def _execute(
        self,
        args: SearchKnowledgeArgs,
        ctx: ToolContext,
    ) -> dict[str, Any]:
        user_id = ctx.current_user.id

        if args.knowledge_base_id is not None:
            # 中文说明：先校验 KB 归属，不能让用户通过显式 id 检索到别人的知识库。
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
            # 中文说明：配置缺失是用户/部署可修复的业务前置错误，不把 AgentRun 标 failed。
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
            # 中文说明：远端不可用或响应坏掉属于系统错误，模型重试同一参数没有帮助。
            # Wrap as system error: the LLM can't fix this by re-prompting,
            # the workflow should mark the run as failed.
            raise ToolSystemError(
                self.name, "embedding_unavailable", str(exc),
            ) from exc

        if not query_vectors:
            # 中文说明：正常 embedding client 不应返回空向量；保留这个分支防御兼容服务异常。
            return {
                "ok": False,
                "error_class": "empty_query_embedding",
                "message_for_llm": "查询向量为空,无法检索。请改写问题后重试。",
                "user_facing_detail": "embedding API returned no vectors",
            }
        query_vec = query_vectors[0]

        # 中文说明：cosine distance 越小越相关；按 user_id 过滤是最核心的 ACL 约束。
        # ``embedding <=> :vec`` (cosine distance). HNSW index on
        # knowledge_chunks.embedding makes this fast even at 10k+ chunks.
        # We filter out null embeddings (failed/pending docs) so the agent
        # never sees stale rows.
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
            # 中文说明：如果 UI/模型指定了知识库，进一步收窄到该 KB；workflow 也会强制覆盖 UI 选择。
            stmt = stmt.where(
                KnowledgeDocument.knowledge_base_id == args.knowledge_base_id,
            )
        stmt = stmt.order_by(distance_expr).limit(args.top_k)

        rows = (await ctx.db.execute(stmt)).all()

        # 中文说明：把 distance 同时映射成 relevance，方便模型用更直观的 0-1 分数判断可信度。
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
                # Map cosine distance [0, 2] → relevance [0, 1] so the
                # LLM has a more intuitive score to reason about.
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

        Default behaviour: a fresh client per call (httpx clients are
        cheap and self-contained).
        """
        return EmbeddingClient()


def _trim(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    # 中文说明：优先在空白处截断，减少给模型看的片段出现半个英文词或半段标记。
    # Cut on a whitespace boundary when possible so the LLM sees a clean
    # truncation rather than a mid-word ellipsis.
    cut = text[:max_chars]
    last_space = cut.rfind(" ")
    if last_space > max_chars - 80:
        cut = cut[:last_space]
    return cut + "…"
