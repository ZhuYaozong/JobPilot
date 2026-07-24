from pathlib import Path

from jobpilot_datasets.config import load_config
from jobpilot_datasets.planning import (
    build_lora_evaluation_plan,
    build_rag_document_plan,
    build_sft_plan,
)


ROOT = Path(__file__).resolve().parents[1]


def test_default_plan_matches_requested_scale() -> None:
    config = load_config(ROOT / "config.yaml")
    sft = build_sft_plan(config)
    documents = build_rag_document_plan(config)
    lora_evaluation = build_lora_evaluation_plan(config)

    assert len(sft) == 3600
    assert sum(item.split == "train" for item in sft) == 3000
    assert sum(item.split == "val" for item in sft) == 300
    assert sum(item.split == "test" for item in sft) == 300
    assert len(documents) == 50
    assert len(lora_evaluation) == 500
    assert len({item.plan_id for item in sft}) == 3600
    assert len({item.plan_id for item in documents}) == 50
    assert len({item.plan_id for item in lora_evaluation}) == 500


def test_plan_is_deterministic() -> None:
    config = load_config(ROOT / "config.yaml")
    first = [item.model_dump() for item in build_sft_plan(config)]
    second = [item.model_dump() for item in build_sft_plan(config)]
    assert first == second


def test_config_fingerprint_does_not_contain_api_key(monkeypatch) -> None:
    monkeypatch.setenv("DATASET_LLM_API_KEY", "top-secret-value")
    config = load_config(ROOT / "config.yaml")
    assert "top-secret-value" not in config.fingerprint


def test_experiment_endpoint_does_not_invalidate_generation_checkpoint() -> None:
    config = load_config(ROOT / "config.yaml")
    original = config.fingerprint
    config.providers["base"].model = "another-base-model"
    assert config.fingerprint == original
