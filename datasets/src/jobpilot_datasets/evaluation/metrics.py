"""检索、参考答案和证据支持度指标。"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from jobpilot_datasets.evaluation.retrieval import SearchResult, tokenize
from jobpilot_datasets.models import AnswerMetrics, RetrievalMetrics


def _multiset_f1(reference: Sequence[str], candidate: Sequence[str]) -> float:
    if not reference or not candidate:
        return 0.0
    reference_counter = Counter(reference)
    candidate_counter = Counter(candidate)
    overlap = sum((reference_counter & candidate_counter).values())
    precision = overlap / len(candidate)
    recall = overlap / len(reference)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _lcs_length(left: Sequence[str], right: Sequence[str]) -> int:
    """滚动数组计算 LCS，避免为长答案分配完整二维矩阵。"""
    if len(left) < len(right):
        left, right = right, left
    previous = [0] * (len(right) + 1)
    for left_item in left:
        current = [0]
        for index, right_item in enumerate(right, start=1):
            if left_item == right_item:
                current.append(previous[index - 1] + 1)
            else:
                current.append(max(current[-1], previous[index]))
        previous = current
    return previous[-1]


def _rouge_l(reference: Sequence[str], candidate: Sequence[str]) -> float:
    if not reference or not candidate:
        return 0.0
    lcs = _lcs_length(reference, candidate)
    precision = lcs / len(candidate)
    recall = lcs / len(reference)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _recall(reference: Sequence[str], candidate: Sequence[str]) -> float:
    if not reference:
        return 0.0
    reference_counter = Counter(reference)
    candidate_counter = Counter(candidate)
    overlap = sum((reference_counter & candidate_counter).values())
    return min(1.0, overlap / sum(reference_counter.values()))


def retrieval_metrics(
    results: list[SearchResult],
    *,
    source_document: str,
    supporting_excerpt: str,
) -> RetrievalMetrics:
    source_ranks = [
        result.rank
        for result in results
        if result.chunk.source_document == source_document
    ]
    hit = 1.0 if source_ranks else 0.0
    reciprocal_rank = 1 / min(source_ranks) if source_ranks else 0.0
    retrieved_text = "\n".join(result.chunk.text for result in results)
    excerpt_recall = _recall(
        tokenize(supporting_excerpt),
        tokenize(retrieved_text),
    )
    return RetrievalMetrics(
        hit_at_k=hit,
        reciprocal_rank=reciprocal_rank,
        excerpt_recall=excerpt_recall,
    )


def answer_metrics(
    reference_answer: str,
    candidate_answer: str,
    supporting_excerpt: str,
) -> AnswerMetrics:
    reference_tokens = tokenize(reference_answer)
    candidate_tokens = tokenize(candidate_answer)
    excerpt_tokens = tokenize(supporting_excerpt)
    return AnswerMetrics(
        token_f1=_multiset_f1(reference_tokens, candidate_tokens),
        rouge_l=_rouge_l(reference_tokens, candidate_tokens),
        source_support=_recall(candidate_tokens, excerpt_tokens),
    )
