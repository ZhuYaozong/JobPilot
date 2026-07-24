from jobpilot_datasets.evaluation.metrics import (
    answer_metrics,
    retrieval_metrics,
)
from jobpilot_datasets.evaluation.retrieval import (
    BM25Retriever,
    DocumentChunk,
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
    assert scores.reciprocal_rank == 1
    assert scores.excerpt_recall > 0.5

    answer_scores = answer_metrics(
        "设置 top k 并使用重排提升相关性",
        "应合理设置 top k，再通过重排提升检索相关性",
        "RAG 检索需要设置 top k，并通过重排提升结果相关性。",
    )
    assert answer_scores.token_f1 > 0.5
    assert answer_scores.rouge_l > 0.5
