"""Base/LoRA Agent eval 对比报告的纯文件测试。"""

from __future__ import annotations

import json
from pathlib import Path

from app.eval.compare import compare_runs, load_run, render_markdown


def _write_run(
    root: Path,
    *,
    model: str,
    passed: bool,
    duration_ms: int,
) -> None:
    root.mkdir(parents=True)
    (root / "summary.md").write_text("# summary\n", encoding="utf-8")
    (root / "run-config.json").write_text(
        json.dumps({
            "model": model,
            "excluded_tools": ["search_knowledge"],
        }),
        encoding="utf-8",
    )
    (root / "case-smoke.json").write_text(
        json.dumps({
            "name": "smoke",
            "passed": passed,
            "duration_ms": duration_ms,
            "trace": {
                "agent_run_status": "succeeded",
                "tool_calls": [{"tool_name": "list_user_jobs"}],
            },
            "assertions": [
                {"type": "tool_called", "passed": passed},
                {"type": "tool_args_contain", "passed": passed},
                {"type": "final_contains", "passed": True},
            ],
        }),
        encoding="utf-8",
    )


def test_compare_aligns_cases_and_renders_metrics(tmp_path: Path) -> None:
    base_dir = tmp_path / "base" / "20260730-120000"
    lora_dir = tmp_path / "lora" / "20260730-120100"
    _write_run(
        base_dir,
        model="jobpilot-base",
        passed=False,
        duration_ms=1000,
    )
    _write_run(
        lora_dir,
        model="jobpilot-lora-v1",
        passed=True,
        duration_ms=500,
    )

    base = load_run(tmp_path / "base", label="Base")
    lora = load_run(tmp_path / "lora", label="LoRA")
    comparison = compare_runs(base, lora)
    markdown = render_markdown(comparison)

    assert comparison["case_set_equal"] is True
    assert comparison["base"]["metrics"]["case_pass_rate"] == 0.0
    assert comparison["lora"]["metrics"]["case_pass_rate"] == 1.0
    assert comparison["base"]["metrics"]["rag_tool_calls"] == 0
    assert "jobpilot-base" in markdown
    assert "jobpilot-lora-v1" in markdown
