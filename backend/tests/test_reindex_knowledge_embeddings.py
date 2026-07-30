import pytest

from scripts.reindex_knowledge_embeddings import parse_vector_dimensions


def test_parse_vector_dimensions() -> None:
    assert parse_vector_dimensions("vector(1024)") == 1024


@pytest.mark.parametrize("value", [None, "vector", "text", "vector(x)"])
def test_parse_vector_dimensions_rejects_unknown_type(value: object) -> None:
    with pytest.raises(RuntimeError, match="无法识别"):
        parse_vector_dimensions(value)
