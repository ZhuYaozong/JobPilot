"""递归字符切片器。

这是一个很小的中文友好切片器，项目约束是不引 ``langchain-text-splitters``。
行为上接近 LangChain 的 ``RecursiveCharacterTextSplitter``，但分隔符优先级按中英
混合求职内容调过：简历笔记、JD、项目复盘里经常同时出现中文标点和英文技术词。

输出保留相对原文的 ``char_start / char_end`` 偏移，方便 ``search_knowledge`` 后续
展示“原文片段”和周边上下文。
"""

from __future__ import annotations

from dataclasses import dataclass


# 分隔符按优先级依次尝试。中文段落常用“。”且不一定有换行，网页复制的 JD 又经常混入
# 英文句号，所以中英文标点都要覆盖。
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
    "",  # 最后兜底：没有任何分隔符时按字符硬切。
)


@dataclass(frozen=True)
class TextChunk:
    """原文中的一个连续切片。

    ``char_start`` 和 ``char_end`` 指向传入 :func:`split_text` 的原始文本，
    不是加 overlap 后的新文本。这样调用方后续可以直接按原文偏移取上下文。
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
    """递归切分文本，保证每个 chunk 不超过 ``chunk_size`` 字符。

    算法分四步：
    1. 从 ``separators`` 里选择第一个出现在当前文本段中的分隔符。
    2. 如果某个片段仍超过 ``chunk_size``，就用下一个分隔符继续递归，优先按自然边界
       切开：段落 → 句子 → 逗号 → 单词/字符。
    3. 把小片段贪心打包回 chunk，直到再放下一个片段会超长。
    4. 每个后续 chunk 前面补上前一个 chunk 尾部的 ``chunk_overlap`` 字符，提高检索召回。

    返回顺序与原文一致；因为 overlap，输出总字符量可能大于输入。非空输入至少返回一个 chunk。
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be in [0, chunk_size)")

    cleaned = text or ""
    if not cleaned.strip():
        return []

    # 先递归切成足够小的片段。segments 保存原文绝对偏移，后续打包时才能算出最终 chunk 的范围。
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
    """把 ``text[start:end]`` 切成多个不超过 ``chunk_size`` 的原文区间。

    ``separators`` 从前往后消耗；当前分隔符切完仍过长的片段，会交给下一层递归继续切。
    """
    span_text = text[start:end]
    if len(span_text) <= chunk_size:
        return [(start, end)] if span_text.strip() else []

    # 找一个当前片段里真实存在的分隔符。这里不用 ``str.split``，因为我们需要原文偏移。
    sep_index = -1
    for idx, sep in enumerate(separators):
        if sep == "":
            sep_index = idx
            break
        if sep in span_text:
            sep_index = idx
            break

    if sep_index == -1:
        # 理论上不会发生，因为默认分隔符最后有 ""；保守起见仍按 chunk_size 硬切。
        return [
            (s, min(s + chunk_size, end))
            for s in range(start, end, chunk_size)
        ]

    sep = separators[sep_index]
    next_separators = separators[sep_index + 1:]

    if sep == "":
        # 没有任何标点/空白时的最后兜底：按 chunk_size 硬切，最后一段可能较短。
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
            # 分隔符留在左侧片段里，保证拼接后不丢原字符；中文标点多为 1 字符，成本很低。
            piece_start, piece_end = cursor, idx + len(sep)
            cursor = idx + len(sep)

        if piece_end - piece_start <= chunk_size:
            if text[piece_start:piece_end].strip():
                out.append((piece_start, piece_end))
        else:
            # 当前分隔符切完仍过大，交给下一优先级分隔符继续递归。
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
    """把相邻小片段贪心打包成不超过 ``chunk_size`` 的 chunks。

    相邻 chunks 之间会把前一个 chunk 末尾的 ``chunk_overlap`` 字符补到下一个 chunk
    开头，避免答案刚好落在边界时检索不到。overlap 从原文取，而不是从“已经拼好的
    前一个 chunk”取，这样即使小片段很多，偏移也仍然清晰。
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
        # 下一个 chunk 从前一个 chunk 的尾部 overlap 开始，再接当前新片段。
        overlap_start = max(cur_start, cur_end - chunk_overlap)
        cur_start = overlap_start
        cur_end = seg_end

    chunks.append(TextChunk(text=text[cur_start:cur_end], char_start=cur_start, char_end=cur_end))
    return chunks
