"""Tests for the OpenAI-compatible embedding client."""

import asyncio
import json

import httpx
import respx

from app.llm.embedding_client import EmbeddingClient


@respx.mock
def test_embedding_client_sends_requested_dimensions() -> None:
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
    )

    vectors = asyncio.run(client.embed(["hello"]))

    assert len(vectors) == 1
    payload = json.loads(route.calls[0].request.content)
    assert payload["model"] == "text-embedding-v4"
    assert payload["input"] == ["hello"]
    assert payload["dimensions"] == 1536
