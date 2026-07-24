import httpx
import pytest
import respx

from jobpilot_datasets.config import ProviderConfig
from jobpilot_datasets.providers.base import GenerationRequest
from jobpilot_datasets.providers.openai_compatible import (
    OpenAICompatibleProvider,
)


@pytest.mark.asyncio
@respx.mock
async def test_openai_compatible_provider_sends_seed_and_json_mode() -> None:
    route = respx.post("https://model.example/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": '{"items":[]}'}}],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                },
            },
        ),
    )
    provider = OpenAICompatibleProvider(
        ProviderConfig(
            kind="openai_compatible",
            base_url="https://model.example/v1",
            api_key="secret",
            model="generator-model",
            max_retries=0,
            json_mode=True,
        ),
    )
    try:
        result = await provider.generate(
            GenerationRequest(
                system_prompt="system",
                user_prompt="user",
                seed=42,
                json_mode=True,
            ),
        )
    finally:
        await provider.close()

    assert result == '{"items":[]}'
    request = route.calls[0].request
    payload = httpx.Response(200, content=request.content).json()
    assert payload["seed"] == 42
    assert payload["response_format"] == {"type": "json_object"}
    assert request.headers["Authorization"] == "Bearer secret"
    assert provider.usage_stats["request_attempts"] == 1
    assert provider.usage_stats["total_tokens"] == 15
