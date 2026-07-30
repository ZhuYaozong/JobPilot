import pytest

from scripts.reindex_knowledge_embeddings import (
    _candidate_statement,
    _migration_candidate_statement,
    build_parser,
    parse_vector_dimensions,
)


def test_parse_vector_dimensions() -> None:
    assert parse_vector_dimensions("vector(1024)") == 1024


@pytest.mark.parametrize("value", [None, "vector", "text", "vector(x)"])
def test_parse_vector_dimensions_rejects_unknown_type(value: object) -> None:
    with pytest.raises(RuntimeError, match="无法识别"):
        parse_vector_dimensions(value)


def _compiled_sql(statement: object) -> str:
    """把 SQLAlchemy 语句编译为带字面量的 SQL，便于断言安全筛选条件。"""
    return str(statement.compile(compile_kwargs={"literal_binds": True}))


def test_candidate_statement_defaults_to_ready_documents() -> None:
    sql = _compiled_sql(_candidate_statement())

    assert "knowledge_documents.status = 'ready'" in sql


def test_candidate_statement_only_includes_non_ready_when_explicit() -> None:
    sql = _compiled_sql(_candidate_statement(include_non_ready=True))

    assert "knowledge_documents.status = 'ready'" not in sql
    assert "knowledge_documents.status != 'ready'" in sql


def test_migration_candidate_statement_counts_all_ready_documents() -> None:
    sql = _compiled_sql(_migration_candidate_statement(after_id=42))

    assert "knowledge_documents.status = 'ready'" in sql
    assert "knowledge_documents.id > 42" in sql
    assert "knowledge_chunks" not in sql


def test_parser_supports_safe_resume_options() -> None:
    args = build_parser().parse_args(
        ["--pre-migration-audit", "--after-id", "42", "--limit", "10"],
    )

    assert args.pre_migration_audit is True
    assert args.after_id == 42
    assert args.limit == 10
    assert args.include_non_ready is False


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["--after-id", "-1"], "必须大于等于 0"),
        (["--batch-size", "0"], "必须大于 0"),
        (["--limit", "0"], "必须大于 0"),
    ],
)
def test_parser_rejects_unsafe_numeric_options(
    arguments: list[str],
    message: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit):
        build_parser().parse_args(arguments)

    assert message in capsys.readouterr().err
