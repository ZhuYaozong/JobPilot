import pytest

from jobpilot_datasets.config import DeduplicationConfig
from jobpilot_datasets.deduplication import QuestionDeduplicator
from jobpilot_datasets.parsing import (
    ModelOutputParseError,
    extract_items,
    parse_json_output,
)


def test_parse_markdown_fenced_json() -> None:
    payload = parse_json_output('```json\n{"items":[{"a":1}]}\n```')
    assert extract_items(payload) == [{"a": 1}]


def test_reject_non_collection_payload() -> None:
    with pytest.raises(ModelOutputParseError):
        extract_items({"value": 1})


def test_deduplicator_finds_exact_and_near_duplicates() -> None:
    dedup = QuestionDeduplicator(
        DeduplicationConfig(
            fuzzy_threshold=88,
            simhash_max_distance=10,
            ngram_size=2,
        ),
    )
    assert dedup.add("one", "如何为 RAG 检索设置超时、重试和降级？") is None

    exact = dedup.check("如何为RAG检索设置超时重试和降级")
    assert exact is not None
    assert exact.kind == "exact"

    near = dedup.check("如何给 RAG 检索设置超时、重试和降级机制？")
    assert near is not None
    assert near.kind == "near"
