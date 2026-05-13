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

    # Embedding endpoint is configured independently from chat completion.
    # Real-world deployments often want a different provider / model for
    # embeddings (e.g. chat from a local Llama, embeddings from OpenAI for
    # higher quality). Each ``embedding_*`` falls back to its ``llm_*``
    # counterpart at access time (see ``EmbeddingClient`` in slice 7'c2),
    # which keeps single-provider setups zero-config while leaving room for
    # the split deployment to take over.
    embedding_base_url: str | None = None
    embedding_api_key: str | None = None
    embedding_model_name: str | None = None
    # 1536 matches OpenAI text-embedding-3-small; override for other models.
    # The DB column is fixed-dim, so changing this requires a migration —
    # keep the value stable per deployment.
    embedding_dimensions: int = 1536

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
