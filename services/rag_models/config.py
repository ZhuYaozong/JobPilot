"""本地 RAG 模型网关的配置。"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


_ENV_FILE = Path(__file__).resolve().with_name(".env")


class RagModelSettings(BaseSettings):
    """集中管理服务监听地址、模型和推理参数。"""

    service_name: str = "JobPilot RAG Models"
    host: str = "127.0.0.1"
    port: int = Field(default=7997, ge=1, le=65_535)

    # 本地笔记本只有一张可见 GPU，显式指定设备可避免模型回落到 CPU。
    device: str = "cuda:0"
    use_fp16: bool = True
    load_models_on_startup: bool = True

    embedding_model: str = "BAAI/bge-m3"
    embedding_model_name: str = "BAAI/bge-m3"
    # BGE-M3 的 dense 向量固定为 1024 维，禁止配置层制造错误契约。
    embedding_dimensions: Literal[1024] = 1024
    embedding_batch_size: int = Field(default=16, ge=1, le=256)
    embedding_max_length: int = Field(default=512, ge=8, le=8192)

    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    reranker_model_name: str = "BAAI/bge-reranker-v2-m3"
    reranker_batch_size: int = Field(default=8, ge=1, le=128)
    reranker_max_length: int = Field(default=512, ge=8, le=8192)
    reranker_normalize_scores: bool = True

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        env_prefix="RAG_MODELS_",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> RagModelSettings:
    """返回进程内复用的配置实例。"""

    return RagModelSettings()
