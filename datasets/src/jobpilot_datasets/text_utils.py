"""文本规范化、计数、哈希和文件名工具。"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path


_MARKDOWN_MARKERS = re.compile(r"[#>*_`\-\[\]\(\)|]")
_WHITESPACE = re.compile(r"\s+")
_PUNCTUATION = re.compile(r"[\W_]+", re.UNICODE)


def visible_char_count(text: str, *, strip_markdown: bool = False) -> int:
    """按 Unicode 可见字符计数；不把空白当成“字数”。"""
    value = _MARKDOWN_MARKERS.sub("", text) if strip_markdown else text
    return len(_WHITESPACE.sub("", value))


def normalize_text(text: str) -> str:
    """用于精确去重的规范化：NFKC、小写、删除标点和空白。"""
    value = unicodedata.normalize("NFKC", text).lower()
    return _PUNCTUATION.sub("", value)


def normalize_for_match(text: str) -> str:
    """用于原文证据匹配，保留字母数字和中文字符。"""
    return normalize_text(_MARKDOWN_MARKERS.sub("", text))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def stable_seed(base_seed: int, key: str) -> int:
    digest = hashlib.sha256(f"{base_seed}:{key}".encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big")


def safe_filename(value: str, *, fallback: str = "document") -> str:
    """保留中文、字母和数字，过滤路径分隔符及 Windows 保留字符。"""
    value = unicodedata.normalize("NFKC", value).strip()
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", value)
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"-+", "-", value).strip(".-")
    return (value or fallback)[:80]


def ensure_within(path: Path, root: Path) -> Path:
    """解析并确认写入路径位于指定根目录，防止配置越界覆盖。"""
    resolved = path.resolve()
    root_resolved = root.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise ValueError(f"路径超出输出根目录: {resolved}")
    return resolved


def strip_yaml_front_matter(markdown: str) -> str:
    lines = markdown.splitlines()
    if len(lines) >= 3 and lines[0].strip() == "---":
        for index in range(1, len(lines)):
            if lines[index].strip() == "---":
                return "\n".join(lines[index + 1 :]).strip()
    return markdown.strip()
