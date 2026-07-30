from pathlib import Path

from jobpilot_datasets.sources import (
    ExternalDocumentImporter,
    FileSystemDocumentSource,
    load_manifest,
)


def test_import_external_text_is_idempotent(test_config, tmp_path: Path) -> None:
    source_file = tmp_path / "external.txt"
    source_file.write_text(
        "外部资料介绍了 RAG 文档切分、检索、重排、超时重试和监控指标。" * 10,
        encoding="utf-8",
    )
    source = FileSystemDocumentSource(
        source_file,
        recursive=False,
        allowed_extensions={".txt"},
    )
    importer = ExternalDocumentImporter(test_config)
    imported, warnings = importer.import_source(source)
    assert len(imported) == 1
    assert not warnings

    imported_again, warnings_again = importer.import_source(source)
    assert not imported_again
    assert any("已导入" in warning for warning in warnings_again)

    manifest_path = (
        test_config.resolve_path(test_config.paths.rag_documents_dir).parent
        / "external_manifest.jsonl"
    )
    assert len(load_manifest(manifest_path)) == 1
