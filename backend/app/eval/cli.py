"""``python -m app.eval.cli`` — 跑全部 eval case 并生成报告。

CLI 选项:
- ``--dataset PATH``:case 来源(默认 ``app/eval/datasets``)。可指向目录
  或单个 .yaml 文件
- ``--filter NAME``:正则,匹配 case.name,只跑命中的
- ``--report-dir DIR``:报告输出根目录(默认 ``./eval-reports``,实际目录
  会带时间戳子目录避免覆盖)
- ``--live``:用真 ``LLMClient`` 替代 fake(需要 ``LLM_*`` env)
- ``--timeout SECONDS``:单 case 超时(默认 120)

退出码:全部 pass → 0;有 fail → 1;CLI 参数错 → 2。
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.eval.cases import EvalCase
from app.eval.loader import load_cases_from_dir, load_cases_from_yaml
from app.eval.report import render_console_lines, write_report
from app.eval.runner import DEFAULT_CASE_TIMEOUT_SECONDS, run_cases


# 默认数据集目录,相对于本文件 → backend/app/eval/datasets/
_DEFAULT_DATASET_DIR = Path(__file__).resolve().parent / "datasets"
_DEFAULT_REPORT_ROOT = Path.cwd() / "eval-reports"


def main(argv: list[str] | None = None) -> int:
    # Windows 控制台默认 GBK,中文 / 部分 Unicode 符号会 encode 失败;
    # Linux / macOS 已经是 UTF-8。统一强制 UTF-8 输出,跑 eval 时报告
    # 永远不会因为编码问题崩在中文行。
    if getattr(sys.stdout, "encoding", "").lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
            sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except Exception:  # noqa: BLE001 — 老 Python / 重定向场景退化
            pass

    parser = _build_parser()
    args = parser.parse_args(argv)

    dataset_path = Path(args.dataset) if args.dataset else _DEFAULT_DATASET_DIR
    if dataset_path.is_dir():
        cases = load_cases_from_dir(dataset_path)
    elif dataset_path.is_file():
        cases = load_cases_from_yaml(dataset_path)
    else:
        print(f"找不到数据集: {dataset_path}", file=sys.stderr)
        return 2

    if args.filter:
        pattern = re.compile(args.filter)
        cases = [c for c in cases if pattern.search(c.name)]

    if not cases:
        print("没有可跑的 case(检查 --filter 是否过严)。", file=sys.stderr)
        return 2

    mode_label = "(LIVE LLM)" if args.live else "(fake LLM)"
    if args.judge and not args.live:
        mode_label += " + judge"
    print(f"准备跑 {len(cases)} 个 case {mode_label}")
    print("=" * 70)

    results = run_cases(
        cases, live=args.live, judge=args.judge, timeout_seconds=args.timeout,
    )

    # 控制台逐条打印 + 最终汇总
    for line in render_console_lines(results):
        print(line)

    passed = sum(1 for r in results if r.passed)
    total = len(results)
    total_ms = sum(r.duration_ms for r in results)
    print("-" * 70)
    print(f"{passed}/{total} passed in {total_ms} ms")

    report_root = Path(args.report_dir) if args.report_dir else _DEFAULT_REPORT_ROOT
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    report_dir = report_root / stamp
    summary_path = write_report(results, report_dir)
    print(f"报告: {summary_path}")

    return 0 if passed == total else 1


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="JobPilot agent eval CLI")
    p.add_argument(
        "--dataset",
        help="case 来源(目录或单 .yaml 文件)。默认 app/eval/datasets/",
    )
    p.add_argument(
        "--filter",
        help="正则匹配 case.name,只跑命中的",
    )
    p.add_argument(
        "--report-dir",
        help="报告输出根目录(默认 ./eval-reports/)",
    )
    p.add_argument(
        "--live",
        action="store_true",
        help="用真 LLMClient,需要 LLM_* env 配置;默认 fake LLM",
    )
    p.add_argument(
        "--judge",
        action="store_true",
        help="启用 LLM-as-judge 评分(llm_judge 断言);--live 隐含 --judge",
    )
    p.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_CASE_TIMEOUT_SECONDS,
        help=f"单 case 超时秒数,默认 {DEFAULT_CASE_TIMEOUT_SECONDS}",
    )
    return p


def collect_cases_for_test(dataset_path: Path | None = None) -> list[EvalCase]:
    """供单测使用的便捷入口:载入指定路径或默认 dataset 目录。"""
    if dataset_path is None:
        return load_cases_from_dir(_DEFAULT_DATASET_DIR)
    return (
        load_cases_from_dir(dataset_path)
        if dataset_path.is_dir()
        else load_cases_from_yaml(dataset_path)
    )


if __name__ == "__main__":
    sys.exit(main())
