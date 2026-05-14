"""OpenAI-compatible Chat Completions 客户端。

业务层只依赖这个很薄的封装：输入 prompt，返回纯文本 content。
这样后续替换模型供应商时，不需要改解析、生成或 Agent workflow 代码。
"""

from typing import Any

import httpx

from app.core.config import settings

# 读超时和连接超时分开设置：本地/国内兼容接口可能连接慢，但生成本身也需要独立预算。
LLM_REQUEST_TIMEOUT_SECONDS = 60.0
LLM_CONNECT_TIMEOUT_SECONDS = 10.0


class LLMConfigError(Exception):
    """缺少必要 LLM 配置时抛出，调用方会转成用户可理解的前置错误。"""

    pass


class LLMClientError(Exception):
    """远端请求失败、响应非法或响应内容为空时抛出。"""

    pass


class LLMClient:
    async def generate_text(self, prompt: str) -> str:
        # 这里做配置短路，避免把半配置状态伪装成远端 401/404 之类的网络错误。
        if (
            not settings.llm_base_url
            or not settings.llm_api_key
            or not settings.llm_model_name
        ):
            raise LLMConfigError("LLM configuration is incomplete")

        # JobPilot 当前统一走 Chat Completions 兼容协议；prompt 作为单轮 user message 输入。
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
            # 每次请求创建独立 AsyncClient，保持 client 无状态，便于测试 monkeypatch。
            timeout = httpx.Timeout(
                LLM_REQUEST_TIMEOUT_SECONDS,
                connect=LLM_CONNECT_TIMEOUT_SECONDS,
            )
            async with httpx.AsyncClient(timeout=timeout) as client:
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
            # 兼容 OpenAI choices[0].message.content 形状；缺字段视为供应商响应不合约。
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMClientError("LLM response content is missing") from exc

        if not isinstance(content, str) or not content.strip():
            raise LLMClientError("LLM response content is empty")
        return content
