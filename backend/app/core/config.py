from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "JobPilot Backend"
    app_env: str = "local"
    app_debug: bool = True
    database_url: str = "postgresql+asyncpg://postgres:123456@localhost:25432/jobpilot"
    redis_url: str = "redis://localhost:26379/0"
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model_name: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
