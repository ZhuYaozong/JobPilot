"""OpenAI 兼容 embedding client 测试。"""

import asyncio
import json

import httpx
import respx

from app.llm.embedding_client import EmbeddingClient


@respx.mock
def test_embedding_client_sends_requested_dimensions_when_enabled() -> None:
    route = respx.post("https://embeddings.example/v1/embeddings").mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"embedding": [0.1] * 1536}]},
        ),
    )

    client = EmbeddingClient(
        base_url="https://embeddings.example/v1",
        api_key="test-key",
        model_name="text-embedding-v4",
        dimensions=1536,
        send_dimensions=True,
    )

    vectors = asyncio.run(client.embed(["hello"]))

    assert len(vectors) == 1
    payload = json.loads(route.calls[0].request.content)
    assert payload["model"] == "text-embedding-v4"
    assert payload["input"] == ["hello"]
    assert payload["dimensions"] == 1536


@respx.mock
def test_embedding_client_omits_dimensions_for_fixed_dimension_model() -> None:
    route = respx.post("https://embeddings.example/v1/embeddings").mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"embedding": [0.1] * 1024}]},
        ),
    )
    client = EmbeddingClient(
        base_url="https://embeddings.example/v1",
        api_key="test-key",
        model_name="BAAI/bge-m3",
        dimensions=1024,
        send_dimensions=False,
    )

    vectors = asyncio.run(client.embed(["hello"]))

    assert len(vectors[0]) == 1024
    payload = json.loads(route.calls[0].request.content)
    assert "dimensions" not in payload


@respx.mock
def test_embedding_client_rejects_unexpected_dimension_when_field_omitted() -> None:
    respx.post("https://embeddings.example/v1/embeddings").mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"embedding": [0.1] * 768}]},
        ),
    )
    client = EmbeddingClient(
        base_url="https://embeddings.example/v1",
        api_key="test-key",
        model_name="BAAI/bge-m3",
        dimensions=1024,
        send_dimensions=False,
    )

    from app.llm.embedding_client import EmbeddingClientError

    try:
        asyncio.run(client.embed(["hello"]))
    except EmbeddingClientError as exc:
        assert "got 768 expected 1024" in str(exc)
    else:
        raise AssertionError("维度不一致时必须拒绝响应")
