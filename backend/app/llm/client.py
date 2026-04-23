from typing import Any

import httpx

from app.core.config import settings


class LLMConfigError(Exception):
    pass


class LLMClientError(Exception):
    pass


class LLMClient:
    async def generate_text(self, prompt: str) -> str:
        if (
            not settings.llm_base_url
            or not settings.llm_api_key
            or not settings.llm_model_name
        ):
            raise LLMConfigError("LLM configuration is incomplete")

        payload: dict[str, Any] = {
            "model": settings.llm_model_name,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            "temperature": 0,
        }
        headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
        url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise LLMClientError("LLM request failed") from exc

        if response.status_code >= 400:
            raise LLMClientError(f"LLM request failed with status {response.status_code}")

        try:
            data = response.json()
        except ValueError as exc:
            raise LLMClientError("LLM response is not valid JSON") from exc
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMClientError("LLM response content is missing") from exc

        if not isinstance(content, str) or not content.strip():
            raise LLMClientError("LLM response content is empty")

        return content
