"""Eval 报告输出:控制台行 + 每 case JSON trace + summary markdown。

报告结构:
    <report-dir>/
      summary.md            汇总(case 表格 + 失败原因)
      case-<name>.json      每 case 的完整 trace + assertion 明细

JSON 用 ASCII safe + 中文 unicode 保留(``ensure_ascii=False``);markdown
表格使用窄列,便于在 PR diff 里看。
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from app.eval.cases import CaseResult


def write_report(results: list[CaseResult], report_dir: Path) -> Path:
    """把 results 写到 ``<report_dir>/summary.md`` + 每 case 的 JSON,
    返回 summary.md 路径。"""
    report_dir.mkdir(parents=True, exist_ok=True)
    for result in results:
        _write_case_json(result, report_dir)
    summary_path = report_dir / "summary.md"
    summary_path.write_text(_render_summary(results), encoding="utf-8")
    return summary_path


def render_console_lines(results: list[CaseResult]) -> list[str]:
    """生成"边跑边打印"的一行总结,CLI 在每个 case 跑完时调用。

    用纯 ASCII 字符标记 pass/fail —— Windows 默认 GBK 控制台编码不接受
    "✓" / "└" 等 Unicode 符号,CI 重定向到文件时也更容易 grep。markdown
    报告里保留 emoji,那是 UTF-8 文件写,没问题。
    """
    lines: list[str] = []
    total = len(results)
    for idx, r in enumerate(results, 1):
        status = "OK" if r.passed else "FAIL"
        line = f"[{idx}/{total}] {r.case.name:<46} [{status}] ({r.duration_ms} ms)"
        lines.append(line)
        if not r.passed:
            if r.error:
                lines.append(f"    - framework error: {r.error}")
            for a in r.assertions:
                if not a.passed:
                    lines.append(f"    - {a.spec.type}: {a.detail}")
        # judge 评分摘要(无论 pass/fail 都显示分数)
        for a in r.assertions:
            if a.score is not None:
                score_pct = f"{a.score:.0%}"
                label = "PASS" if a.passed else "FAIL"
                lines.append(f"    - judge: {score_pct} [{label}]")
                if a.judge_detail and a.judge_detail.get("aspects"):
                    for asp in a.judge_detail["aspects"]:
                        lines.append(
                            f"      {asp.get('name','?')}: "
                            f"{asp.get('score',0)}/{asp.get('max',5)} "
                            f"- {asp.get('reason','')}"
                        )
    return lines


# ---------- 内部实现 -------------------------------------------------------


def _write_case_json(result: CaseResult, report_dir: Path) -> None:
    payload = {
        "name": result.case.name,
        "description": result.case.description,
        "passed": result.passed,
        "duration_ms": result.duration_ms,
        "error": result.error,
        "user_text": result.case.user_text,
        "context": result.case.context,
        "trace": asdict(result.trace) if result.trace else None,
        "assertions": [
            {
                "type": a.spec.type,
                "params": a.spec.params,
                "passed": a.passed,
                "detail": a.detail,
                **({"score": a.score} if a.score is not None else {}),
                **({"judge_detail": a.judge_detail} if a.judge_detail else {}),
            }
            for a in result.assertions
        ],
    }
    safe_name = _slugify(result.case.name)
    (report_dir / f"case-{safe_name}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _render_summary(results: list[CaseResult]) -> str:
    """生成 summary.md。"""
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    total_ms = sum(r.duration_ms for r in results)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    out: list[str] = []
    out.append(f"# JobPilot Agent Eval — {now}\n")
    out.append(
        f"**{passed}/{total} passed**(总耗时 {total_ms} ms,平均 "
        f"{total_ms / max(total, 1):.0f} ms / case)\n",
    )
    out.append("\n## 结果表\n")
    out.append("| # | case | 结果 | 耗时 | 说明 |\n")
    out.append("|---|---|---|---|---|\n")
    for idx, r in enumerate(results, 1):
        verdict = "✅ pass" if r.passed else "❌ fail"
        first_fail = ""
        if not r.passed:
            if r.error:
                first_fail = f"框架: {r.error[:80]}"
            else:
                for a in r.assertions:
                    if not a.passed:
                        first_fail = f"{a.spec.type}: {a.detail[:80]}"
                        break
        out.append(
            f"| {idx} | `{r.case.name}` | {verdict} | {r.duration_ms} ms |"
            f" {first_fail.replace('|', '\\|')} |\n",
        )

    # judge 评分汇总(所有含 judge 的 case,无论 pass/fail)
    judge_cases = [
        r for r in results
        if any(a.score is not None for a in r.assertions)
    ]
    if judge_cases:
        out.append("\n## LLM Judge 评分\n")
        out.append("| case | 总分 | 结果 | 各维度 |\n")
        out.append("|---|---|---|---|\n")
        for r in judge_cases:
            for a in r.assertions:
                if a.score is not None:
                    verdict = "✅" if a.passed else "❌"
                    aspects_str = ""
                    if a.judge_detail and a.judge_detail.get("aspects"):
                        parts = [
                            f"{asp.get('name','?')} {asp.get('score',0)}/{asp.get('max',5)}"
                            for asp in a.judge_detail["aspects"]
                        ]
                        aspects_str = ", ".join(parts)
                    out.append(
                        f"| `{r.case.name}` | {a.score:.0%} | {verdict} |"
                        f" {aspects_str.replace('|', '\\|')} |\n",
                    )

    failures = [r for r in results if not r.passed]
    if failures:
        out.append("\n## 失败明细\n")
        for r in failures:
            out.append(f"\n### `{r.case.name}`\n")
            if r.case.description:
                out.append(f"_{r.case.description}_\n")
            if r.error:
                out.append(f"\n**框架错误**: `{r.error}`\n")
            for a in r.assertions:
                if not a.passed:
                    out.append(f"- ❌ `{a.spec.type}`: {a.detail}\n")
                    # judge 失败时附上各维度明细
                    if a.judge_detail and a.judge_detail.get("aspects"):
                        for asp in a.judge_detail["aspects"]:
                            out.append(
                                f"  - {asp.get('name','?')}: "
                                f"{asp.get('score',0)}/{asp.get('max',5)} "
                                f"— {asp.get('reason','')}\n",
                            )
                        if a.judge_detail.get("reasoning"):
                            out.append(f"  - _评语_: {a.judge_detail['reasoning'][:200]}\n")
            if r.trace:
                tool_names = [tc.get("tool_name") for tc in r.trace.tool_calls]
                out.append(
                    f"\n_工具调用顺序_: `{tool_names}`,_status_: "
                    f"`{r.trace.agent_run_status}`\n",
                )
                if r.trace.final_text:
                    snippet = r.trace.final_text[:240]
                    out.append(f"\n_final_text 前 240 字_:\n\n> {snippet}\n")
    return "".join(out)


def _slugify(name: str) -> str:
    """文件名安全化:替换非 ASCII 和路径分隔符。"""
    safe: list[str] = []
    for ch in name:
        if ch.isalnum() or ch in {"-", "_"}:
            safe.append(ch)
        else:
            safe.append("_")
    return "".join(safe).strip("_") or "case"
