"""Recursive character-based text splitter.

A small (~80 LOC) Chinese-aware splitter written ourselves rather than
pulling in langchain-text-splitters. Behaviour matches LangChain's
``RecursiveCharacterTextSplitter`` in spirit but with separator priorities
tuned for mixed CN/EN job-search content (resume notes, JDs, project
write-ups).

The output preserves ``char_start / char_end`` offsets into the original
text so the agent's ``search_knowledge`` tool (slice 7'c3) can later show
"原文片段" with the surrounding context.
"""

from __future__ import annotations

from dataclasses import dataclass


# Separator priority — try each in order. Mixing CN/EN punctuation matters
# because Chinese paragraphs often end in 。 with no following \n, and JDs
# pasted from web pages often have stray ASCII full-stops.
DEFAULT_SEPARATORS: tuple[str, ...] = (
    "\n\n",
    "\n",
    "。",
    "！",
    "？",
    ".",
    "!",
    "?",
    "；",
    ";",
    "，",
    ",",
    " ",
    "",  # final fallback: split mid-character
)


@dataclass(frozen=True)
class TextChunk:
    """One contiguous slice of the source text.

    ``char_start`` and ``char_end`` are byte-character offsets into the
    *original* text passed to :func:`split_text`, **not** the post-overlap
    concatenation. This lets callers grab surrounding context later by
    slicing the source directly.
    """

    text: str
    char_start: int
    char_end: int


def split_text(
    text: str,
    *,
    chunk_size: int = 800,
    chunk_overlap: int = 100,
    separators: tuple[str, ...] = DEFAULT_SEPARATORS,
) -> list[TextChunk]:
    """Recursively split ``text`` into chunks of at most ``chunk_size`` chars.

    Algorithm:
    1. Pick the first separator from ``separators`` that appears in the
       remaining text. Split on it.
    2. For each segment, if it still exceeds ``chunk_size``, recurse with
       the *next* separator. This biases splits toward "natural" boundaries
       (paragraph → sentence → comma → word).
    3. Greedy-pack segments back together up to ``chunk_size``, emitting
       a chunk when the next segment would overflow.
    4. Add ``chunk_overlap`` characters of trailing text from the previous
       chunk to the start of each subsequent chunk for retrieval recall.

    Returns chunks in source order; total emitted character count >= input
    length (because of overlap). Always returns at least one chunk for
    non-empty input.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be in [0, chunk_size)")

    cleaned = text or ""
    if not cleaned.strip():
        return []

    # Recursive split into segments small enough that *every* one is
    # ``<= chunk_size``. ``segments`` keeps absolute (start, end) offsets
    # so packing later can compute the chunk's own offsets correctly.
    segments = _recursive_split_with_offsets(
        cleaned, 0, len(cleaned), chunk_size, list(separators),
    )

    return _pack_with_overlap(cleaned, segments, chunk_size, chunk_overlap)


def _recursive_split_with_offsets(
    text: str,
    start: int,
    end: int,
    chunk_size: int,
    separators: list[str],
) -> list[tuple[int, int]]:
    """Split ``text[start:end]`` into spans each <= chunk_size.

    ``separators`` is consumed front-to-back: the head is tried first, the
    rest is passed to deeper recursion if a segment is still oversized.
    """
    span_text = text[start:end]
    if len(span_text) <= chunk_size:
        return [(start, end)] if span_text.strip() else []

    # Find a separator that actually appears in this span. We avoid
    # ``str.split`` because we need offsets, not just substrings.
    sep_index = -1
    for idx, sep in enumerate(separators):
        if sep == "":
            sep_index = idx
            break
        if sep in span_text:
            sep_index = idx
            break

    if sep_index == -1:
        # No usable separator at all (shouldn't happen because "" is last
        # in the default list); fall back to hard cut at chunk_size.
        return [
            (s, min(s + chunk_size, end))
            for s in range(start, end, chunk_size)
        ]

    sep = separators[sep_index]
    next_separators = separators[sep_index + 1:]

    if sep == "":
        # Hard slice — last resort when no punctuation/whitespace anywhere.
        # Yields runs of exactly chunk_size (last possibly shorter).
        return [
            (s, min(s + chunk_size, end))
            for s in range(start, end, chunk_size)
        ]

    out: list[tuple[int, int]] = []
    cursor = start
    while cursor < end:
        idx = text.find(sep, cursor, end)
        if idx == -1:
            piece_start, piece_end = cursor, end
            cursor = end
        else:
            # Keep the separator on the LEFT piece so concatenated text
            # retains the original characters. Many CN punctuations are
            # 1 char so this is cheap.
            piece_start, piece_end = cursor, idx + len(sep)
            cursor = idx + len(sep)

        if piece_end - piece_start <= chunk_size:
            if text[piece_start:piece_end].strip():
                out.append((piece_start, piece_end))
        else:
            # Still too big — descend with the next separator.
            out.extend(
                _recursive_split_with_offsets(
                    text, piece_start, piece_end, chunk_size, next_separators,
                ),
            )
    return out


def _pack_with_overlap(
    text: str,
    segments: list[tuple[int, int]],
    chunk_size: int,
    chunk_overlap: int,
) -> list[TextChunk]:
    """Greedy-pack neighbouring segments into chunks up to ``chunk_size``.

    Between consecutive chunks we prepend the trailing ``chunk_overlap``
    characters of the previous chunk so retrieval recall doesn't suffer at
    chunk boundaries. The overlap region is taken from the *source text*
    (not "the last N chars of the previous chunk after concatenation"), so
    it stays meaningful even when individual segments are tiny.
    """
    if not segments:
        return []

    chunks: list[TextChunk] = []
    cur_start = segments[0][0]
    cur_end = segments[0][1]
    for seg_start, seg_end in segments[1:]:
        new_size = seg_end - cur_start
        if new_size <= chunk_size:
            cur_end = seg_end
            continue
        chunks.append(TextChunk(text=text[cur_start:cur_end], char_start=cur_start, char_end=cur_end))
        # Start the next chunk with overlap_from_prev + the new segment.
        overlap_start = max(cur_start, cur_end - chunk_overlap)
        cur_start = overlap_start
        cur_end = seg_end

    chunks.append(TextChunk(text=text[cur_start:cur_end], char_start=cur_start, char_end=cur_end))
    return chunks
