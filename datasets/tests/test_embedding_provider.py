import httpx
import pytest
import respx

from jobpilot_datasets.config import ProviderConfig
from jobpilot_datasets.evaluation.embedding import OpenAIEmbeddingProvider
from jobpilot_datasets.providers.base import ProviderRequestError


@pytest.mark.asyncio
@respx.mock
async def test_bge_embedding_omits_dimensions_and_validates_output() -> None:
    route = respx.post("https://embedding.example/v1/embeddings").mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"index": 0, "embedding": [0.1] * 1024}]},
        ),
    )
    provider = OpenAIEmbeddingProvider(
        ProviderConfig(
            kind="openai_compatible",
            base_url="https://embedding.example/v1",
            model="BAAI/bge-m3",
            dimensions=1024,
            send_dimensions=False,
        ),
    )
    try:
        vectors = await provider.embed(["hello"])
    finally:
        await provider.close()

    payload = httpx.Response(200, content=route.calls[0].request.content).json()
    assert "dimensions" not in payload
    assert len(vectors[0]) == 1024


@pytest.mark.asyncio
@respx.mock
async def test_bge_embedding_rejects_dimension_mismatch() -> None:
    respx.post("https://embedding.example/v1/embeddings").mock(
        return_value=httpx.Response(
            200,
            json={"data": [{"index": 0, "embedding": [0.1] * 768}]},
        ),
    )
    provider = OpenAIEmbeddingProvider(
        ProviderConfig(
            kind="openai_compatible",
            base_url="https://embedding.example/v1",
            model="BAAI/bge-m3",
            dimensions=1024,
        ),
    )
    try:
        with pytest.raises(ProviderRequestError, match="expected=1024"):
            await provider.embed(["hello"])
    finally:
        await provider.close()
