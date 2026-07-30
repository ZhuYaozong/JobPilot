"""search_knowledge — Agent 的 RAG 检索工具。

这个工具只暴露稳定的 Agent 参数和结果契约，底层由 RetrievalService 根据配置
选择 vector、bm25 或 hybrid，并可选执行 rerank。它只读知识库，不写业务数据。

权限边界必须始终按 ``user_id`` 过滤，即使 ``knowledge_base_id`` 为空也不能跨用户。
``knowledge_chunks.user_id`` 是专门为这个查询路径冗余的字段，避免每次检索都靠
多层 join 才能确认归属。

工具结果会进入 ``format_response``，由 LLM 基于召回内容生成回答。
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
from app.rag.factory import build_retrieval_service
from app.rag.reranker import RerankerError
from app.rag.service import RetrievalService
from app.rag.vector import EmptyQueryEmbeddingError


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
        "按当前 RAG 策略检索用户知识库内容，例如公司背景、项目笔记、面试资料等。"
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
            hits = await self._retrieval_service().search(
                ctx.db,
                query=args.query,
                user_id=user_id,
                knowledge_base_id=args.knowledge_base_id,
                top_k=args.top_k,
            )
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
        except EmptyQueryEmbeddingError as exc:
            return {
                "ok": False,
                "error_class": "empty_query_embedding",
                "message_for_llm": "查询向量为空,无法检索。请改写问题后重试。",
                "user_facing_detail": str(exc),
            }
        except RerankerError as exc:
            raise ToolSystemError(
                self.name, "reranker_unavailable", str(exc),
            ) from exc

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

    def _retrieval_service(self) -> RetrievalService:
        """统一装配入口，同时保留原测试替换 embedding client 的钩子。"""
        return build_retrieval_service(
            embedding_client_factory=self._embedding_client,
        )
