from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "JobPilot Backend"
    app_env: str = "local"
    app_debug: bool = True
    database_url: str = "postgresql+asyncpg://postgres:123456@127.0.0.1:25432/jobpilot"
    redis_url: str = "redis://127.0.0.1:26379/0"
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model_name: str | None = None

    # embedding 端点独立于聊天补全端点配置。真实部署常常会拆供应商/模型：
    # 例如聊天走本地 Llama，向量化走中文质量更好的 OpenAI 兼容服务。
    # 每个 ``embedding_*`` 会在调用时回退到对应的 ``llm_*``，既让单供应商部署零额外配置，
    # 又给拆分部署留出口。
    embedding_base_url: str | None = None
    embedding_api_key: str | None = None
    embedding_model_name: str | None = None
    # BGE-M3 的 dense embedding 固定为 1024 维。数据库向量列也是固定维度，
    # 换模型时必须配套 migration，并在每个部署环境内保持配置稳定。
    embedding_dimensions: int = Field(default=1024, ge=1)
    # 部分 OpenAI-compatible 服务支持 dimensions，原生 BGE 服务通常不接受该字段。
    # 无论是否发送，EmbeddingClient 都会校验服务实际返回的向量维度。
    embedding_send_dimensions: bool = False

    # 隔离验证集确认等权 Hybrid + Rerank 质量最高，因此作为默认生产策略。
    rag_strategy: Literal["vector", "bm25", "hybrid"] = "hybrid"
    rag_candidate_multiplier: int = Field(default=3, ge=1, le=20)
    rag_bm25_k1: float = Field(default=1.5, gt=0)
    rag_bm25_b: float = Field(default=0.75, ge=0, le=1)
    rag_hybrid_rrf_k: int = Field(default=60, ge=1)
    rag_vector_weight: float = Field(default=1.0, gt=0)
    rag_bm25_weight: float = Field(default=1.0, gt=0)
    # Hybrid 下 embedding 不可用时允许退化到 BM25，纯 vector 模式仍保留旧错误语义。
    rag_hybrid_vector_fail_open: bool = True

    # Reranker 使用通用 POST /rerank 协议；默认启用，失败时保留 Hybrid 融合排序。
    rag_reranker_enabled: bool = True
    rag_reranker_fail_open: bool = True
    reranker_base_url: str | None = None
    reranker_api_key: str | None = None
    reranker_model_name: str | None = None
    reranker_timeout_seconds: float = Field(default=15.0, gt=0)

    # 认证配置
    # auth_dev_mode=True 时同时接受 X-User-Name header（向后兼容开发模式）；
    # 生产部署应设为 False，仅允许 JWT token 认证。
    auth_secret_key: str = "jobpilot-dev-secret-change-in-production"
    auth_algorithm: str = "HS256"
    auth_access_token_expire_minutes: int = 1440  # 24 小时
    auth_dev_mode: bool = True

    # MCP Client 配置。服务器清单使用 JSON，避免在代码里保存 URL 或凭证；
    # 每个服务器的 token 只保存对应环境变量名，真实 token 不进入配置对象和日志。
    mcp_enabled: bool = False
    mcp_servers_json: str = "[]"
    mcp_discovery_timeout_seconds: float = 5.0
    mcp_call_timeout_seconds: float = 15.0
    mcp_discovery_cache_seconds: int = 60
    mcp_max_result_chars: int = 20_000

    # 独立 JobPilot MCP Server 配置。默认只监听本机并复用 JobPilot JWT。
    mcp_server_host: str = "127.0.0.1"
    mcp_server_port: int = 8001
    mcp_server_public_url: str = "http://127.0.0.1:8001/mcp"
    mcp_server_issuer_url: str = "http://127.0.0.1:8000"
    mcp_token_expire_minutes: int = 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
