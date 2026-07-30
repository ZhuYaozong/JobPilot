import pytest

from conftest import DeterministicEmbeddingProvider
from jobpilot_datasets.evaluation.metrics import (
    answer_metrics,
    retrieval_metrics,
)
from jobpilot_datasets.evaluation.retrieval import (
    BM25Retriever,
    DocumentChunk,
    HybridRetriever,
    VectorRetriever,
)


def test_bm25_and_metrics_find_source_document() -> None:
    chunks = [
        DocumentChunk(
            chunk_id="rag/documents/a.md#0",
            source_document="rag/documents/a.md",
            text="RAG 检索需要设置 top k，并通过重排提升结果相关性。",
        ),
        DocumentChunk(
            chunk_id="rag/documents/b.md#0",
            source_document="rag/documents/b.md",
            text="模型部署需要关注批处理与 KV Cache。",
        ),
    ]
    results = BM25Retriever(chunks).search("RAG 检索如何设置 top k", top_k=2)
    scores = retrieval_metrics(
        results,
        source_document="rag/documents/a.md",
        supporting_excerpt="RAG 检索需要设置 top k",
    )
    assert scores.hit_at_k == 1
    assert scores.recall_at_k == 1
    assert scores.reciprocal_rank == 1
    assert scores.excerpt_recall > 0.5

    answer_scores = answer_metrics(
        "设置 top k 并使用重排提升相关性",
        "应合理设置 top k，再通过重排提升检索相关性",
        "RAG 检索需要设置 top k，并通过重排提升结果相关性。",
    )
    assert answer_scores.token_f1 > 0.5
    assert answer_scores.rouge_l > 0.5
    assert answer_scores.answer_score > 0.5
    assert answer_scores.faithfulness > 0.5


def test_excerpt_recall_ignores_matching_words_from_wrong_source() -> None:
    results = BM25Retriever(
        [
            DocumentChunk(
                chunk_id="wrong#0",
                source_document="wrong.md",
                text="监控指标包括失败率、P95 延迟和错误分类。",
            ),
        ],
    ).search("监控指标有哪些", top_k=1)

    scores = retrieval_metrics(
        results,
        source_document="gold.md",
        supporting_excerpt="监控指标包括失败率和 P95 延迟。",
    )

    assert scores.recall_at_k == 0
    assert scores.reciprocal_rank == 0
    assert scores.excerpt_recall == 0


@pytest.mark.asyncio
async def test_vector_and_hybrid_follow_common_retriever_interface() -> None:
    chunks = [
        DocumentChunk("a#0", "a", "Python RAG 混合检索"),
        DocumentChunk("b#0", "b", "前端样式与颜色"),
    ]
    vector = VectorRetriever(chunks, DeterministicEmbeddingProvider())
    bm25 = BM25Retriever(chunks)
    hybrid = HybridRetriever(vector, bm25, rrf_k=10)

    vector_results = await vector.retrieve("RAG 检索", top_k=2)
    hybrid_results = await hybrid.retrieve("RAG 检索", top_k=2)

    assert vector_results[0].retrieval_source == "vector"
    assert hybrid_results[0].retrieval_source == "hybrid"
    assert hybrid_results[0].chunk.chunk_id == "a#0"
