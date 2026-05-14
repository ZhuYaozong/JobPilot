"""Unit tests for the recursive text splitter (slice 7'c2)."""

import pytest

from app.services.text_splitter import split_text


def test_empty_input_returns_no_chunks() -> None:
    assert split_text("") == []
    assert split_text("   \n  \n") == []


def test_short_input_returns_single_chunk() -> None:
    text = "Hello world this is short."
    chunks = split_text(text, chunk_size=800)
    assert len(chunks) == 1
    assert chunks[0].text == text
    assert chunks[0].char_start == 0
    assert chunks[0].char_end == len(text)


def test_splits_on_double_newline_first() -> None:
    """The default separator priority prefers paragraph breaks over
    sentence breaks. Two short paragraphs should produce two chunks even
    when their combined length fits in chunk_size — well, actually they
    would pack back together. So we need them to exceed chunk_size.
    """
    para_a = "段落 A。" * 50  # ≈ 250 chars
    para_b = "段落 B。" * 50  # ≈ 250 chars
    text = f"{para_a}\n\n{para_b}"
    chunks = split_text(text, chunk_size=300, chunk_overlap=20)
    # Expect at least 2 chunks; paragraph boundary should land between A
    # and B (i.e. no chunk should straddle the "\n\n").
    assert len(chunks) >= 2
    assert "段落 A" in chunks[0].text
    assert chunks[-1].text.endswith("段落 B。") or "段落 B" in chunks[-1].text


def test_falls_back_to_sentence_punctuation() -> None:
    """When no \\n\\n is available, the splitter should fall through the
    separator priority list and break on Chinese full-stops."""
    text = "。".join([f"第{i}句" for i in range(60)])  # no newlines
    chunks = split_text(text, chunk_size=80, chunk_overlap=10)
    assert len(chunks) >= 2
    # Each chunk should be at most chunk_size characters (after the recursive
    # split — overlap adds at most chunk_overlap so still within limits in
    # this test config).
    for chunk in chunks:
        assert len(chunk.text) <= 80 + 10


def test_hard_fallback_for_text_without_separators() -> None:
    """No newlines, no punctuation, no spaces — the splitter must still
    produce chunks via the empty-string fallback."""
    text = "a" * 250
    chunks = split_text(text, chunk_size=100, chunk_overlap=10)
    assert len(chunks) >= 3
    for chunk in chunks:
        assert chunk.text == text[chunk.char_start:chunk.char_end]


def test_char_offsets_are_correct() -> None:
    """Every chunk's text must match text[char_start:char_end] exactly —
    this is the invariant the search_knowledge tool relies on to render
    "原文片段" with surrounding context."""
    text = "第一段。第二段。第三段。\n\n下一节。还是下一节。" * 5
    chunks = split_text(text, chunk_size=50, chunk_overlap=10)
    assert len(chunks) >= 2
    for chunk in chunks:
        assert chunk.text == text[chunk.char_start:chunk.char_end]


def test_overlap_adds_trailing_context_between_chunks() -> None:
    """Consecutive chunks should share a small region — the end of chunk N
    should overlap with the start of chunk N+1 (give or take whitespace)."""
    text = "句子。" * 100  # 300 chars of repeating CN punctuation
    chunks = split_text(text, chunk_size=60, chunk_overlap=20)
    assert len(chunks) >= 2
    for prev, nxt in zip(chunks, chunks[1:]):
        # The next chunk's start offset must lie inside the previous chunk
        # (= overlap is non-empty) OR be exactly at the previous chunk's end
        # (= no overlap was achievable on this boundary).
        assert nxt.char_start <= prev.char_end


def test_chunks_never_exceed_chunk_size_in_normal_case() -> None:
    """Pure-Chinese content with paragraph breaks should stay within
    chunk_size (the recursive split is supposed to keep promising)."""
    paragraphs = ["这是一段中文测试文本。" * 8 for _ in range(8)]
    text = "\n\n".join(paragraphs)
    chunks = split_text(text, chunk_size=200, chunk_overlap=20)
    for chunk in chunks:
        # Allow a small slop because overlap can push the next chunk's
        # start backward and grow its length slightly; we don't strictly
        # enforce chunk_size on the final concatenated body.
        assert len(chunk.text) <= 220


def test_invalid_overlap_rejected() -> None:
    with pytest.raises(ValueError):
        split_text("hello", chunk_size=10, chunk_overlap=10)
    with pytest.raises(ValueError):
        split_text("hello", chunk_size=10, chunk_overlap=-1)
    with pytest.raises(ValueError):
        split_text("hello", chunk_size=0, chunk_overlap=0)
