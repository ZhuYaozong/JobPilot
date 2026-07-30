"""适配中文技术问题的精确与近似去重。"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

from rapidfuzz.fuzz import ratio

from jobpilot_datasets.config import DeduplicationConfig
from jobpilot_datasets.text_utils import normalize_text, sha256_text


def _ngrams(text: str, size: int) -> set[str]:
    if not text:
        return set()
    if len(text) <= size:
        return {text}
    return {text[index : index + size] for index in range(len(text) - size + 1)}


def _simhash(features: set[str]) -> int:
    if not features:
        return 0
    vector = [0] * 64
    for feature in features:
        digest = int(sha256_text(feature)[:16], 16)
        for bit in range(64):
            vector[bit] += 1 if digest & (1 << bit) else -1
    fingerprint = 0
    for bit, value in enumerate(vector):
        if value >= 0:
            fingerprint |= 1 << bit
    return fingerprint


def _hamming(left: int, right: int) -> int:
    return (left ^ right).bit_count()


@dataclass(frozen=True, slots=True)
class DuplicateMatch:
    existing_id: str
    kind: str
    similarity: float


@dataclass(slots=True)
class _Entry:
    record_id: str
    normalized: str
    fingerprint: int
    ngrams: set[str]


class QuestionDeduplicator:
    """用倒排 n-gram 缩小候选集，再用 SimHash 和编辑相似度复核。"""

    def __init__(self, config: DeduplicationConfig) -> None:
        self.config = config
        self._entries: list[_Entry] = []
        self._exact: dict[str, int] = {}
        self._ngram_index: dict[str, set[int]] = defaultdict(set)
        self._simhash_buckets: dict[tuple[int, int], set[int]] = defaultdict(set)

    def __len__(self) -> int:
        return len(self._entries)

    def check(self, text: str) -> DuplicateMatch | None:
        normalized = normalize_text(text)
        if not normalized:
            return DuplicateMatch("", "empty", 100.0)
        exact_key = sha256_text(normalized)
        exact_index = self._exact.get(exact_key)
        if exact_index is not None:
            entry = self._entries[exact_index]
            return DuplicateMatch(entry.record_id, "exact", 100.0)

        grams = _ngrams(normalized, self.config.ngram_size)
        fingerprint = _simhash(grams)
        candidates: set[int] = set()

        # SimHash 分桶负责召回结构相似问题。
        for segment in range(4):
            bucket = (fingerprint >> (segment * 16)) & 0xFFFF
            candidates.update(self._simhash_buckets.get((segment, bucket), set()))

        # n-gram 倒排负责召回中文同义改写中的大量共享片段。
        overlap_counts: Counter[int] = Counter()
        for gram in grams:
            overlap_counts.update(self._ngram_index.get(gram, set()))
        minimum_overlap = max(1, int(len(grams) * 0.3))
        candidates.update(
            index
            for index, overlap in overlap_counts.items()
            if overlap >= minimum_overlap
        )

        for index in candidates:
            entry = self._entries[index]
            similarity = float(ratio(normalized, entry.normalized))
            distance = _hamming(fingerprint, entry.fingerprint)
            if (
                similarity >= self.config.fuzzy_threshold
                or (
                    distance <= self.config.simhash_max_distance
                    and similarity >= self.config.fuzzy_threshold - 5
                )
            ):
                return DuplicateMatch(entry.record_id, "near", similarity)
        return None

    def add(self, record_id: str, text: str) -> DuplicateMatch | None:
        match = self.check(text)
        if match is not None:
            return match

        normalized = normalize_text(text)
        grams = _ngrams(normalized, self.config.ngram_size)
        fingerprint = _simhash(grams)
        entry = _Entry(record_id, normalized, fingerprint, grams)
        index = len(self._entries)
        self._entries.append(entry)
        self._exact[sha256_text(normalized)] = index
        for gram in grams:
            self._ngram_index[gram].add(index)
        for segment in range(4):
            bucket = (fingerprint >> (segment * 16)) & 0xFFFF
            self._simhash_buckets[(segment, bucket)].add(index)
        return None
