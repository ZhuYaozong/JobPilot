"""实验用 BM25、Vector 与 Hybrid Retriever。"""

from __future__ import annotations

import math
import re
import asyncio
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from jobpilot_datasets.evaluation.embedding import EmbeddingProvider

from jobpilot_datasets.text_utils import ensure_within, strip_yaml_front_matter


_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+|[\u3400-\u9fff]+")


def tokenize(text: str) -> list[str]:
    """英文按词、中文按单字和双字切分，兼顾技术缩写与中文短语。"""
    tokens: list[str] = []
    for match in _TOKEN_PATTERN.findall(text.lower()):
        if re.fullmatch(r"[\u3400-\u9fff]+", match):
            tokens.extend(match)
            tokens.extend(
                match[index : index + 2]
                for index in range(len(match) - 1)
            )
        else:
            tokens.append(match)
    return tokens


@dataclass(frozen=True, slots=True)
class DocumentChunk:
    chunk_id: str
    source_document: str
    text: str


@dataclass(frozen=True, slots=True)
class SearchResult:
    chunk: DocumentChunk
    score: float
    rank: int
    retrieval_source: str = "bm25"


class Retriever(Protocol):
    """实验召回器统一异步接口。"""

    async def retrieve(self, query: str, *, top_k: int) -> list[SearchResult]: ...


def chunk_document(
    source_document: str,
    content: str,
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> list[DocumentChunk]:
    """按字符窗口切分，并尽量在段落边界结束。"""
    text = strip_yaml_front_matter(content).strip()
    if not text:
        return []
    chunks: list[DocumentChunk] = []
    start = 0
    index = 0
    while start < len(text):
        tentative_end = min(start + chunk_size, len(text))
        end = tentative_end
        if tentative_end < len(text):
            paragraph_end = text.rfind("\n\n", start + chunk_size // 2, tentative_end)
            if paragraph_end > start:
                end = paragraph_end
        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append(
                DocumentChunk(
                    chunk_id=f"{source_document}#chunk-{index:04d}",
                    source_document=source_document,
                    text=chunk_text,
                ),
            )
            index += 1
        if end >= len(text):
            break
        next_start = max(end - chunk_overlap, start + 1)
        start = next_start
    return chunks


class BM25Retriever:
    """用于建立可复现检索基线，也可作为未来向量检索适配器的对照组。"""

    def __init__(
        self,
        chunks: list[DocumentChunk],
        *,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        self.chunks = chunks
        self.k1 = k1
        self.b = b
        self.term_frequencies = [Counter(tokenize(chunk.text)) for chunk in chunks]
        self.lengths = [sum(counter.values()) for counter in self.term_frequencies]
        self.average_length = (
            sum(self.lengths) / len(self.lengths) if self.lengths else 0
        )
        document_frequency: Counter[str] = Counter()
        for counter in self.term_frequencies:
            document_frequency.update(counter.keys())
        total = len(chunks)
        self.idf = {
            term: math.log(1 + (total - frequency + 0.5) / (frequency + 0.5))
            for term, frequency in document_frequency.items()
        }

    def search(self, query: str, *, top_k: int) -> list[SearchResult]:
        if not self.chunks:
            return []
        query_terms = Counter(tokenize(query))
        scored: list[tuple[int, float]] = []
        for index, frequencies in enumerate(self.term_frequencies):
            score = 0.0
            length = self.lengths[index]
            for term, query_frequency in query_terms.items():
                frequency = frequencies.get(term, 0)
                if frequency == 0:
                    continue
                denominator = frequency + self.k1 * (
                    1
                    - self.b
                    + self.b
                    * length
                    / max(self.average_length, 1)
                )
                score += (
                    self.idf.get(term, 0)
                    * frequency
                    * (self.k1 + 1)
                    / denominator
                    * query_frequency
                )
            if score > 0:
                scored.append((index, score))
        scored.sort(key=lambda item: (-item[1], self.chunks[item[0]].chunk_id))
        return [
            SearchResult(
                chunk=self.chunks[index],
                score=score,
                rank=rank,
            )
            for rank, (index, score) in enumerate(scored[:top_k], start=1)
        ]

    async def retrieve(self, query: str, *, top_k: int) -> list[SearchResult]:
        """异步接口适配；保留 search 供旧调用方使用。"""
        return self.search(query, top_k=top_k)


class VectorRetriever:
    """在实验语料上构建可复现的内存向量索引。"""

    def __init__(
        self,
        chunks: list[DocumentChunk],
        embedding_provider: EmbeddingProvider,
    ) -> None:
        self.chunks = chunks
        self.embedding_provider = embedding_provider
        self._vectors: list[list[float]] | None = None
        self._index_lock = asyncio.Lock()

    async def retrieve(self, query: str, *, top_k: int) -> list[SearchResult]:
        if not self.chunks:
            return []
        if self._vectors is None:
            # 并发 case 共用一个 Retriever，只允许构建一次语料向量索引。
            async with self._index_lock:
                if self._vectors is None:
                    self._vectors = await self.embedding_provider.embed(
                        [chunk.text for chunk in self.chunks],
                    )
        query_vectors = await self.embedding_provider.embed([query])
        if not query_vectors:
            return []
        scored = [
            (index, _cosine_similarity(query_vectors[0], vector))
            for index, vector in enumerate(self._vectors)
        ]
        scored.sort(key=lambda item: (-item[1], self.chunks[item[0]].chunk_id))
        return [
            SearchResult(
                chunk=self.chunks[index],
                score=score,
                rank=rank,
                retrieval_source="vector",
            )
            for rank, (index, score) in enumerate(scored[:top_k], start=1)
        ]


class HybridRetriever:
    """使用加权 RRF 融合向量与 BM25 排名。"""

    def __init__(
        self,
        vector: Retriever,
        bm25: Retriever,
        *,
        rrf_k: int = 60,
        vector_weight: float = 1.0,
        bm25_weight: float = 1.0,
    ) -> None:
        self.vector = vector
        self.bm25 = bm25
        self.rrf_k = rrf_k
        self.vector_weight = vector_weight
        self.bm25_weight = bm25_weight

    async def retrieve(self, query: str, *, top_k: int) -> list[SearchResult]:
        vector_results = await self.vector.retrieve(query, top_k=top_k)
        bm25_results = await self.bm25.retrieve(query, top_k=top_k)
        scores: dict[str, float] = {}
        chunks: dict[str, DocumentChunk] = {}
        for results, weight in (
            (vector_results, self.vector_weight),
            (bm25_results, self.bm25_weight),
        ):
            for result in results:
                chunk_id = result.chunk.chunk_id
                chunks.setdefault(chunk_id, result.chunk)
                scores[chunk_id] = scores.get(chunk_id, 0.0) + (
                    weight / (self.rrf_k + result.rank)
                )
        ordered = sorted(scores, key=lambda item: (-scores[item], item))[:top_k]
        return [
            SearchResult(
                chunk=chunks[chunk_id],
                score=scores[chunk_id],
                rank=rank,
                retrieval_source="hybrid",
            )
            for rank, chunk_id in enumerate(ordered, start=1)
        ]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    """计算余弦相似度并对零向量、维度漂移做显式保护。"""
    if len(left) != len(right):
        raise ValueError("embedding 维度不一致")
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def load_chunks(
    output_root: Path,
    source_documents: list[str],
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    for source_document in sorted(set(source_documents)):
        path = ensure_within(output_root / source_document, output_root)
        if not path.exists():
            continue
        chunks.extend(
            chunk_document(
                source_document,
                path.read_text(encoding="utf-8"),
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            ),
        )
    return chunks
