from functools import lru_cache

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
    # 1536 对应 OpenAI text-embedding-3-small；换模型时需要同步修改。
    # 数据库向量列是固定维度，改这里必须配套 migration，每个部署环境内要保持稳定。
    embedding_dimensions: int = 1536

    # 认证配置
    # auth_dev_mode=True 时同时接受 X-User-Name header（向后兼容开发模式）；
    # 生产部署应设为 False，仅允许 JWT token 认证。
    auth_secret_key: str = "jobpilot-dev-secret-change-in-production"
    auth_algorithm: str = "HS256"
    auth_access_token_expire_minutes: int = 1440  # 24 小时
    auth_dev_mode: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
