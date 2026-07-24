"""测试与本地流程演练使用的 Provider。"""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable

from jobpilot_datasets.providers.base import (
    GenerationRequest,
    ProviderRequestError,
    ProviderUsageStats,
)


class FakeProvider:
    """按顺序返回预置响应，不访问网络。"""

    def __init__(self, responses: Iterable[str]) -> None:
        self.responses = deque(responses)
        self.requests: list[GenerationRequest] = []
        self._usage = ProviderUsageStats()

    async def generate(self, request: GenerationRequest) -> str:
        self.requests.append(request)
        self._usage.request_attempts += 1
        if not self.responses:
            self._usage.failed_attempts += 1
            raise ProviderRequestError("FakeProvider 没有剩余响应")
        self._usage.successful_responses += 1
        return self.responses.popleft()

    async def close(self) -> None:
        return None

    @property
    def usage_stats(self) -> dict[str, int]:
        return self._usage.snapshot()
