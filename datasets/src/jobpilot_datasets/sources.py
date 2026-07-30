"""外部文档导入与 RAG 文档清单。"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol

from jobpilot_datasets.config import AppConfig
from jobpilot_datasets.io_utils import (
    atomic_write_jsonl,
    atomic_write_text,
    read_jsonl,
)
from jobpilot_datasets.models import DocumentManifestItem
from jobpilot_datasets.text_utils import (
    safe_filename,
    sha256_text,
    visible_char_count,
)


class DocumentExtractionError(RuntimeError):
    """外部文档格式不支持或解析失败。"""


class DocumentSource(Protocol):
    """后续接入网页、对象存储或数据库时实现此接口。"""

    def discover(self) -> Iterable[Path]:
        ...

    def extract(self, path: Path) -> str:
        ...


class FileSystemDocumentSource:
    """支持 Markdown、文本，以及可选的 PDF/DOCX。"""

    def __init__(
        self,
        source: Path,
        *,
        recursive: bool,
        allowed_extensions: set[str],
    ) -> None:
        self.source = source.expanduser().resolve()
        self.recursive = recursive
        self.allowed_extensions = {item.lower() for item in allowed_extensions}

    def discover(self) -> Iterable[Path]:
        if self.source.is_file():
            candidates = [self.source]
        elif self.source.is_dir():
            pattern = "**/*" if self.recursive else "*"
            candidates = sorted(path for path in self.source.glob(pattern) if path.is_file())
        else:
            raise FileNotFoundError(f"外部文档路径不存在: {self.source}")
        return [
            path
            for path in candidates
            if path.suffix.lower() in self.allowed_extensions
        ]

    def extract(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in {".md", ".txt"}:
            for encoding in ("utf-8-sig", "utf-8", "gb18030"):
                try:
                    return path.read_text(encoding=encoding)
                except UnicodeDecodeError:
                    continue
            raise DocumentExtractionError(f"无法识别文本编码: {path.name}")
        if suffix == ".pdf":
            try:
                from pypdf import PdfReader
            except ImportError as exc:
                raise DocumentExtractionError(
                    "导入 PDF 前请安装：uv sync --extra documents",
                ) from exc
            reader = PdfReader(path)
            return "\n\n".join(page.extract_text() or "" for page in reader.pages)
        if suffix == ".docx":
            try:
                from docx import Document
            except ImportError as exc:
                raise DocumentExtractionError(
                    "导入 DOCX 前请安装：uv sync --extra documents",
                ) from exc
            document = Document(path)
            return "\n\n".join(paragraph.text for paragraph in document.paragraphs)
        raise DocumentExtractionError(f"不支持的外部文档格式: {suffix}")


class ExternalDocumentImporter:
    """把外部文档规范化为 Markdown，并写入来源清单。"""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.documents_dir = config.resolve_path(config.paths.rag_documents_dir)
        self.output_root = config.resolve_path(Path("."))
        self.manifest_path = self.documents_dir.parent / "external_manifest.jsonl"

    def import_source(
        self,
        source: DocumentSource,
    ) -> tuple[list[DocumentManifestItem], list[str]]:
        existing = {
            item.sha256: item
            for item in load_manifest(self.manifest_path)
        }
        imported: list[DocumentManifestItem] = []
        warnings: list[str] = []

        for path in source.discover():
            try:
                extracted = source.extract(path).strip()
            except Exception as exc:  # 单个文件失败不阻断批量导入
                warnings.append(f"{path.name}: {type(exc).__name__}: {exc}")
                continue
            if visible_char_count(extracted, strip_markdown=True) < (
                self.config.external_documents.minimum_chars
            ):
                warnings.append(f"{path.name}: 有效内容过短，已跳过")
                continue

            digest = sha256_text(extracted)
            if digest in existing:
                warnings.append(f"{path.name}: 内容已导入，已跳过")
                continue
            target_name = (
                f"external-{safe_filename(path.stem)}-{digest[:8]}.md"
            )
            target = self.documents_dir / target_name
            title_prefix = "" if extracted.lstrip().startswith("#") else f"# {path.stem}\n\n"
            front_matter = (
                "---\n"
                "source_type: external\n"
                f"source_file: {path.name}\n"
                f"source_sha256: {digest}\n"
                "---\n\n"
            )
            atomic_write_text(target, front_matter + title_prefix + extracted + "\n")
            relative = target.relative_to(self.output_root).as_posix()
            item = DocumentManifestItem(
                plan_id=f"external-{digest[:16]}",
                path=relative,
                source_type="external",
                sha256=digest,
                original_name=path.name,
            )
            existing[digest] = item
            imported.append(item)

        atomic_write_jsonl(
            self.manifest_path,
            [
                item.model_dump(mode="json")
                for item in sorted(existing.values(), key=lambda value: value.path)
            ],
        )
        return imported, warnings


def load_manifest(path: Path) -> list[DocumentManifestItem]:
    if not path.exists():
        return []
    return [
        DocumentManifestItem.model_validate(payload)
        for _, payload in read_jsonl(path)
    ]


def selected_document_manifests(config: AppConfig) -> list[DocumentManifestItem]:
    documents_dir = config.resolve_path(config.paths.rag_documents_dir)
    records: list[DocumentManifestItem] = []
    if config.rag_evaluation.include_generated_documents:
        records.extend(load_manifest(documents_dir.parent / "generated_manifest.jsonl"))
    if config.rag_evaluation.include_external_documents:
        records.extend(load_manifest(documents_dir.parent / "external_manifest.jsonl"))

    # 按 path 去重，并过滤清单中已经不存在的文件。
    output_root = config.resolve_path(Path("."))
    selected: dict[str, DocumentManifestItem] = {}
    for record in records:
        candidate = (output_root / record.path).resolve()
        if candidate.exists():
            selected[record.path] = record
    return sorted(selected.values(), key=lambda item: item.path)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
