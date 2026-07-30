"""JSON/JSONL 与原子文件写入工具。"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any


class JsonlReadError(ValueError):
    """JSONL 某一行无法解析。"""

    def __init__(self, path: Path, line: int, message: str) -> None:
        super().__init__(f"{path}:{line}: {message}")
        self.path = path
        self.line = line


def read_jsonl(path: Path) -> Iterator[tuple[int, dict[str, Any]]]:
    """逐行读取对象型 JSONL，并保留行号用于质量报告。"""
    with path.open("r", encoding="utf-8") as file:
        for line_number, raw_line in enumerate(file, start=1):
            if not raw_line.strip():
                continue
            try:
                payload = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise JsonlReadError(path, line_number, str(exc)) from exc
            if not isinstance(payload, dict):
                raise JsonlReadError(path, line_number, "每一行必须是 JSON 对象")
            yield line_number, payload


def atomic_write_text(path: Path, content: str) -> None:
    """在目标目录创建临时文件后原子替换，避免中断留下半文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as file:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def atomic_write_json(path: Path, payload: Any) -> None:
    content = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    atomic_write_text(path, content)


def atomic_write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    lines = [
        json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        for record in records
    ]
    atomic_write_text(path, "\n".join(lines) + ("\n" if lines else ""))


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    """checkpoint 采用只追加 JSONL；最终数据仍使用原子整体写入。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as file:
        file.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
        file.write("\n")
        file.flush()
        os.fsync(file.fileno())
