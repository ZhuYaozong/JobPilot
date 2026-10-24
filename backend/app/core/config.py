from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import SecretStr, Field, field_validator, model_validator
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
    # 默认只接受 JWT；开发头需在 local/test 中显式开启并提供用户名。
    # 其他环境统一按服务部署处理，不允许开发认证与默认密钥。
    auth_secret_key: str = "jobpilot-dev-secret-change-in-production"
    auth_algorithm: str = "HS256"
    auth_access_token_expire_minutes: int = 1440  # 24 小时
    auth_dev_mode: bool = False

    # 外部身份独立启用；以下地址由部署者固定，不能由请求或 token 选择。
    delegated_auth_enabled: bool = False
    delegated_issuer: str = ""
    delegated_jwks_url: str = ""
    delegated_introspection_url: str = ""
    delegated_client_id: str = "jobpilot"
    delegated_client_secret: SecretStr = SecretStr("")
    delegated_audience: str = "jobpilot"
    delegated_actor_clients: dict[str, Literal["tiki", "platform"]] = Field(default_factory=lambda: {"tiki": "tiki"})
    delegated_timeout_seconds: float = Field(default=3.0, gt=0, le=10)
    delegated_jwks_cache_seconds: int = Field(default=300, ge=5, le=300)
    delegated_max_lifetime_seconds: int = Field(default=600, ge=30, le=3600)

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

    @field_validator("app_env")
    @classmethod
    def normalize_app_env(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("APP_ENV 不能为空")
        return normalized

    @model_validator(mode="after")
    def validate_auth_environment(self):
        # 不识别的环境名称也按服务部署处理，避免拼写错误绕过保护。
        if self.app_env not in {"local", "test"}:
            if self.auth_dev_mode:
                raise ValueError("服务环境禁止 AUTH_DEV_MODE")
            if self.app_debug:
                raise ValueError("服务环境必须关闭 APP_DEBUG")
            placeholders = {
                "jobpilot-dev-secret-change-in-production",
                "change-this-to-a-long-random-secret",
                "jobpilot-isolated-test-only",
            }
            if self.auth_secret_key.strip() in placeholders or len(self.auth_secret_key.strip().encode("utf-8")) < 32:
                raise ValueError("服务环境 AUTH_SECRET_KEY 必须使用至少 32 字节的非示例密钥")
            if self.auth_algorithm != "HS256":
                raise ValueError("当前服务认证只支持 HS256；外部令牌由独立验证入口接入")
        return self

    @model_validator(mode="after")
    def validate_delegated_auth(self):
        if not self.delegated_auth_enabled:
            return self
        urls = [self.delegated_issuer, self.delegated_jwks_url, self.delegated_introspection_url]
        try:
            parsed = [urlsplit(value) for value in urls]
            for value, url in zip(urls, parsed):
                if value != value.strip() or url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
                    raise ValueError("endpoint")
                if url.port is not None and not 1 <= url.port <= 65535:
                    raise ValueError("port")
            origins = {(url.hostname, url.port or 443) for url in parsed}
            if len(origins) != 1 or not 1 <= len(self.delegated_issuer.encode()) <= 512:
                raise ValueError("origin")
            if any(not url.path.startswith(parsed[0].path.rstrip("/") + "/") for url in parsed[1:]):
                raise ValueError("issuer path")
            if self.delegated_jwks_url == self.delegated_introspection_url:
                raise ValueError("different endpoints")
        except ValueError:
            raise ValueError("受托身份必须配置同一 HTTPS 身份源下的 issuer/JWKS/introspection 地址") from None
        if not self.delegated_client_id.strip() or not self.delegated_audience.strip() or not self.delegated_client_secret.get_secret_value().strip():
            raise ValueError("受托身份必须配置 client_id、client_secret 与 audience")
        if not self.delegated_actor_clients or any(not key.strip() for key in self.delegated_actor_clients):
            raise ValueError("受托身份必须配置可信调用方到 actor 的映射")
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
