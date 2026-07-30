"""比较两次 JobPilot Agent eval 结果并生成并排报告。

典型用法：

    python -m app.eval.compare \
      --base-dir eval-reports/base \
      --lora-dir eval-reports/lora \
      --output-dir eval-reports/comparison

输入既可以是包含 ``summary.md`` 的单次目录，也可以是 CLI 生成时间戳
子目录的报告根目录；后一种情况自动选择最新一次运行。
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_ASSERTION_GROUPS: dict[str, set[str]] = {
    "工具路由": {
        "tool_called",
        "tool_not_called",
        "tool_order",
        "tool_call_count",
    },
    "工具参数": {"tool_args_contain"},
    "最终回复": {
        "final_contains",
        "final_matches_regex",
        "final_question_count",
    },
}


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        base = load_run(Path(args.base_dir), label=args.base_label)
        lora = load_run(Path(args.lora_dir), label=args.lora_label)
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))

    comparison = compare_runs(base, lora)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "comparison.json"
    markdown_path = output_dir / "comparison.md"
    json_path.write_text(
        json.dumps(comparison, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    markdown_path.write_text(render_markdown(comparison), encoding="utf-8")
    print(f"对比报告: {markdown_path}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="比较 Base/LoRA Agent eval 报告")
    parser.add_argument("--base-dir", required=True, help="Base 报告目录或报告根目录")
    parser.add_argument("--lora-dir", required=True, help="LoRA 报告目录或报告根目录")
    parser.add_argument("--output-dir", required=True, help="对比报告输出目录")
    parser.add_argument("--base-label", default="Base", help="Base 列显示名")
    parser.add_argument("--lora-label", default="LoRA", help="LoRA 列显示名")
    return parser


def load_run(path: Path, *, label: str) -> dict[str, Any]:
    """载入一次运行的配置和所有 case JSON。"""
    run_dir = _resolve_run_dir(path)
    config_path = run_dir / "run-config.json"
    config = (
        json.loads(config_path.read_text(encoding="utf-8"))
        if config_path.exists()
        else {}
    )
    cases: dict[str, dict[str, Any]] = {}
    for case_path in sorted(run_dir.glob("case-*.json")):
        payload = json.loads(case_path.read_text(encoding="utf-8"))
        name = payload.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"case 文件缺少有效 name: {case_path}")
        cases[name] = payload
    if not cases:
        raise ValueError(f"报告目录没有 case-*.json: {run_dir}")
    return {
        "label": label,
        "run_dir": str(run_dir.resolve()),
        "config": config,
        "cases": cases,
    }


def _resolve_run_dir(path: Path) -> Path:
    """解析单次报告目录；传根目录时选择最新的时间戳子目录。"""
    if (path / "summary.md").is_file():
        return path
    if not path.exists():
        raise FileNotFoundError(f"报告路径不存在: {path}")
    candidates = [item.parent for item in path.rglob("summary.md")]
    if not candidates:
        raise FileNotFoundError(f"路径下找不到 summary.md: {path}")
    return max(candidates, key=lambda item: (item / "summary.md").stat().st_mtime)


def compare_runs(base: dict[str, Any], lora: dict[str, Any]) -> dict[str, Any]:
    """按同名 case 对齐两次运行并计算客观指标。"""
    base_names = set(base["cases"])
    lora_names = set(lora["cases"])
    all_names = sorted(base_names | lora_names)

    rows: list[dict[str, Any]] = []
    for name in all_names:
        base_case = base["cases"].get(name)
        lora_case = lora["cases"].get(name)
        rows.append({
            "name": name,
            "base": _case_brief(base_case),
            "lora": _case_brief(lora_case),
        })

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base": {
            "label": base["label"],
            "run_dir": base["run_dir"],
            "config": base["config"],
            "metrics": _aggregate(base["cases"]),
        },
        "lora": {
            "label": lora["label"],
            "run_dir": lora["run_dir"],
            "config": lora["config"],
            "metrics": _aggregate(lora["cases"]),
        },
        "case_set_equal": base_names == lora_names,
        "only_in_base": sorted(base_names - lora_names),
        "only_in_lora": sorted(lora_names - base_names),
        "cases": rows,
    }


def _case_brief(case: dict[str, Any] | None) -> dict[str, Any] | None:
    if case is None:
        return None
    trace = case.get("trace") or {}
    failures = [
        assertion.get("type")
        for assertion in case.get("assertions") or []
        if not assertion.get("passed")
    ]
    return {
        "passed": bool(case.get("passed")),
        "duration_ms": int(case.get("duration_ms") or 0),
        "agent_run_status": trace.get("agent_run_status"),
        "tool_sequence": [
            call.get("tool_name") for call in trace.get("tool_calls") or []
        ],
        "failed_assertions": failures,
    }


def _aggregate(cases: dict[str, dict[str, Any]]) -> dict[str, Any]:
    payloads = list(cases.values())
    total = len(payloads)
    passed = sum(bool(case.get("passed")) for case in payloads)
    durations = [int(case.get("duration_ms") or 0) for case in payloads]
    workflow_succeeded = sum(
        (case.get("trace") or {}).get("agent_run_status") == "succeeded"
        for case in payloads
    )
    rag_calls = sum(
        call.get("tool_name") == "search_knowledge"
        for case in payloads
        for call in (case.get("trace") or {}).get("tool_calls") or []
    )

    grouped = {
        label: _assertion_rate(payloads, types)
        for label, types in _ASSERTION_GROUPS.items()
    }
    return {
        "case_total": total,
        "case_passed": passed,
        "case_pass_rate": passed / total if total else 0.0,
        "workflow_succeeded": workflow_succeeded,
        "workflow_success_rate": workflow_succeeded / total if total else 0.0,
        "average_duration_ms": sum(durations) / total if total else 0.0,
        "rag_tool_calls": rag_calls,
        "assertion_groups": grouped,
    }


def _assertion_rate(
    cases: list[dict[str, Any]],
    included_types: set[str],
) -> dict[str, Any]:
    selected = [
        assertion
        for case in cases
        for assertion in case.get("assertions") or []
        if assertion.get("type") in included_types
    ]
    passed = sum(bool(assertion.get("passed")) for assertion in selected)
    total = len(selected)
    return {
        "passed": passed,
        "total": total,
        "rate": passed / total if total else None,
    }


def render_markdown(comparison: dict[str, Any]) -> str:
    """把对比结果渲染成适合复盘和面试讲述的 Markdown。"""
    base = comparison["base"]
    lora = comparison["lora"]
    base_metrics = base["metrics"]
    lora_metrics = lora["metrics"]
    base_label = base["label"]
    lora_label = lora["label"]

    out = ["# JobPilot Agent Base / LoRA 对比\n\n"]
    out.append("## 实验配置\n\n")
    out.append(f"- {base_label} 模型：`{base['config'].get('model', '')}`\n")
    out.append(f"- {lora_label} 模型：`{lora['config'].get('model', '')}`\n")
    out.append(
        f"- RAG 隔离：Base 排除 `{base['config'].get('excluded_tools', [])}`；"
        f"LoRA 排除 `{lora['config'].get('excluded_tools', [])}`\n",
    )
    out.append(f"- case 集一致：`{comparison['case_set_equal']}`\n\n")

    out.append("## 汇总指标\n\n")
    out.append(f"| 指标 | {base_label} | {lora_label} |\n")
    out.append("|---|---:|---:|\n")
    out.append(
        f"| case 通过率 | {_pct(base_metrics['case_pass_rate'])} "
        f"({base_metrics['case_passed']}/{base_metrics['case_total']}) | "
        f"{_pct(lora_metrics['case_pass_rate'])} "
        f"({lora_metrics['case_passed']}/{lora_metrics['case_total']}) |\n",
    )
    out.append(
        f"| Agent 成功率 | {_pct(base_metrics['workflow_success_rate'])} | "
        f"{_pct(lora_metrics['workflow_success_rate'])} |\n",
    )
    for group in _ASSERTION_GROUPS:
        base_group = base_metrics["assertion_groups"][group]
        lora_group = lora_metrics["assertion_groups"][group]
        out.append(
            f"| {group}断言通过率 | {_rate_cell(base_group)} | "
            f"{_rate_cell(lora_group)} |\n",
        )
    out.append(
        f"| 平均耗时 | {base_metrics['average_duration_ms']:.0f} ms | "
        f"{lora_metrics['average_duration_ms']:.0f} ms |\n",
    )
    out.append(
        f"| RAG 工具调用次数 | {base_metrics['rag_tool_calls']} | "
        f"{lora_metrics['rag_tool_calls']} |\n",
    )

    out.append("\n## 逐 case 对比\n\n")
    out.append(f"| case | {base_label} | {lora_label} | 工具轨迹 |\n")
    out.append("|---|---|---|---|\n")
    for row in comparison["cases"]:
        base_case = row["base"]
        lora_case = row["lora"]
        base_cell = _case_cell(base_case)
        lora_cell = _case_cell(lora_case)
        trajectories = (
            f"B: `{(base_case or {}).get('tool_sequence', [])}`<br>"
            f"L: `{(lora_case or {}).get('tool_sequence', [])}`"
        )
        out.append(
            f"| `{row['name']}` | {base_cell} | {lora_cell} | {trajectories} |\n",
        )
    return "".join(out)


def _case_cell(case: dict[str, Any] | None) -> str:
    if case is None:
        return "缺失"
    verdict = "✅" if case["passed"] else "❌"
    failures = ", ".join(case["failed_assertions"]) or "-"
    return f"{verdict} {case['duration_ms']} ms<br>{failures}"


def _rate_cell(group: dict[str, Any]) -> str:
    if group["rate"] is None:
        return "N/A"
    return f"{_pct(group['rate'])} ({group['passed']}/{group['total']})"


def _pct(value: float) -> str:
    return f"{value:.1%}"


if __name__ == "__main__":
    raise SystemExit(main())
