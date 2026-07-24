"""模型生成接口，数据流水线不依赖具体推理后端。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    """单次模型请求。batch 指一段 Prompt 中要求返回多条记录。"""

    system_prompt: str
    user_prompt: str
    seed: int
    temperature: float | None = None
    max_tokens: int | None = None
    json_mode: bool = False


@dataclass(slots=True)
class ProviderUsageStats:
    """跨 Provider 统一的调用与 token 统计。"""

    request_attempts: int = 0
    successful_responses: int = 0
    failed_attempts: int = 0
    usage_reported_responses: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    prompt_cache_hit_tokens: int = 0
    prompt_cache_miss_tokens: int = 0

    def snapshot(self) -> dict[str, int]:
        return asdict(self)


class GenerationProvider(Protocol):
    """OpenAI-compatible、本地 Qwen 和测试替身的共同接口。"""

    async def generate(self, request: GenerationRequest) -> str:
        """生成一段文本。"""
        ...

    async def close(self) -> None:
        """释放网络连接或模型资源。"""
        ...

    @property
    def usage_stats(self) -> dict[str, int]:
        """返回当前进程累计调用统计。"""
        ...


class ProviderConfigurationError(RuntimeError):
    """Provider 缺少运行所需配置。"""


class ProviderRequestError(RuntimeError):
    """模型请求在重试后仍失败。"""
