"""无外部服务依赖的 BM25 基线检索器。"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

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
