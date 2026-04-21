from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "JobPilot Backend"
    app_env: str = "local"
    app_debug: bool = True
    database_url: str = "postgresql+asyncpg://postgres:123456@localhost:25432/jobpilot"
    redis_url: str = "redis://localhost:26379/0"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
