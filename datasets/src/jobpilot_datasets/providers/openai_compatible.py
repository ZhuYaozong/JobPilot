"""OpenAI-compatible Chat Completions Provider。"""

from __future__ import annotations

import asyncio
import os
import random
from typing import Any

import httpx

from jobpilot_datasets.config import ProviderConfig
from jobpilot_datasets.providers.base import (
    GenerationRequest,
    ProviderConfigurationError,
    ProviderRequestError,
    ProviderUsageStats,
)


class OpenAICompatibleProvider:
    """支持云端 OpenAI API、vLLM、SGLang 等兼容端点。"""

    def __init__(self, config: ProviderConfig) -> None:
        if not config.base_url.strip():
            raise ProviderConfigurationError("OpenAI-compatible Provider 缺少 base_url")
        if not config.model.strip():
            raise ProviderConfigurationError("OpenAI-compatible Provider 缺少 model")
        self.config = config
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(config.timeout_seconds, connect=20),
        )
        # 正式生产时可临时调高并发；该运行参数不改变数据配置和 checkpoint 指纹。
        runtime_concurrency = int(
            os.getenv("DATASET_RUNTIME_CONCURRENCY", str(config.concurrency)),
        )
        self.concurrency = max(1, min(runtime_concurrency, 64))
        self._semaphore = asyncio.Semaphore(self.concurrency)
        self._usage = ProviderUsageStats()

    async def generate(self, request: GenerationRequest) -> str:
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "temperature": (
                self.config.temperature
                if request.temperature is None
                else request.temperature
            ),
            "max_tokens": request.max_tokens or self.config.max_tokens,
        }
        if self.config.send_seed:
            payload["seed"] = request.seed
        # 部分本地兼容端点不支持 response_format，可在 Provider 配置中关闭。
        if request.json_mode and self.config.json_mode:
            payload["response_format"] = {"type": "json_object"}
        payload.update(self.config.extra_body)

        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        url = f"{self.config.base_url.rstrip('/')}/chat/completions"

        last_error: Exception | None = None
        async with self._semaphore:
            for attempt in range(self.config.max_retries + 1):
                try:
                    self._usage.request_attempts += 1
                    response = await self._client.post(
                        url,
                        headers=headers,
                        json=payload,
                    )
                    response.raise_for_status()
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    if not isinstance(content, str) or not content.strip():
                        raise ValueError("模型响应 content 为空")
                    self._usage.successful_responses += 1
                    self._record_usage(data.get("usage"))
                    return content
                except (
                    httpx.HTTPError,
                    KeyError,
                    IndexError,
                    TypeError,
                    ValueError,
                ) as exc:
                    self._usage.failed_attempts += 1
                    last_error = exc
                    if attempt >= self.config.max_retries:
                        break
                    # 抖动只影响等待时间，不影响任务 seed 和数据划分。
                    delay = min(2**attempt, 16) + random.random() * 0.25
                    await asyncio.sleep(delay)

        raise ProviderRequestError(
            f"模型请求失败，已尝试 {self.config.max_retries + 1} 次",
        ) from last_error

    async def close(self) -> None:
        await self._client.aclose()

    @property
    def usage_stats(self) -> dict[str, int]:
        return self._usage.snapshot()

    def _record_usage(self, usage: Any) -> None:
        if not isinstance(usage, dict):
            return
        self._usage.usage_reported_responses += 1
        for field in (
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "prompt_cache_hit_tokens",
            "prompt_cache_miss_tokens",
        ):
            value = usage.get(field, 0)
            if isinstance(value, int) and value >= 0:
                setattr(self._usage, field, getattr(self._usage, field) + value)
