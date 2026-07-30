"""容错解析模型返回的 JSON。"""

from __future__ import annotations

import json
from json import JSONDecodeError
from typing import Any


class ModelOutputParseError(ValueError):
    """模型输出无法解析或超出安全长度。"""


def parse_json_output(raw: str, *, max_chars: int = 100_000) -> Any:
    """兼容裸 JSON、Markdown fence 和 JSON 前后的少量说明文字。"""
    if len(raw) > max_chars:
        raise ModelOutputParseError(
            f"模型响应长度 {len(raw)} 超过上限 {max_chars}",
        )
    text = raw.strip()
    candidates = [text]

    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        candidates.append("\n".join(lines).strip())

    object_start, object_end = text.find("{"), text.rfind("}")
    if object_start >= 0 and object_end > object_start:
        candidates.append(text[object_start : object_end + 1])
    array_start, array_end = text.find("["), text.rfind("]")
    if array_start >= 0 and array_end > array_start:
        candidates.append(text[array_start : array_end + 1])

    errors: list[str] = []
    for candidate in dict.fromkeys(candidates):
        try:
            return json.loads(candidate)
        except JSONDecodeError as exc:
            errors.append(str(exc))
    raise ModelOutputParseError("模型响应不是有效 JSON: " + " | ".join(errors[:2]))


def extract_items(payload: Any) -> list[dict[str, Any]]:
    """接受 JSON 数组或 {"items": [...]}，并拒绝非对象元素。"""
    items = payload.get("items") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise ModelOutputParseError("模型响应必须是数组或包含 items 数组的对象")
    if not all(isinstance(item, dict) for item in items):
        raise ModelOutputParseError("items 中的每一项都必须是对象")
    return items
