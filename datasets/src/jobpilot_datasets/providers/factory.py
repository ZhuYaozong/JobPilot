"""根据配置创建模型 Provider。"""

from __future__ import annotations

from jobpilot_datasets.config import AppConfig
from jobpilot_datasets.providers.base import GenerationProvider
from jobpilot_datasets.providers.openai_compatible import OpenAICompatibleProvider
from jobpilot_datasets.providers.qwen_local import QwenLocalProvider


def create_provider(config: AppConfig, name: str) -> GenerationProvider:
    """创建命名 Provider；fake 只允许在测试中显式注入，避免误跑空数据。"""
    provider_config = config.providers[name]
    if provider_config.kind == "openai_compatible":
        return OpenAICompatibleProvider(provider_config)
    if provider_config.kind == "qwen_local":
        return QwenLocalProvider(provider_config)
    raise ValueError("fake Provider 需要在测试代码中显式注入")
