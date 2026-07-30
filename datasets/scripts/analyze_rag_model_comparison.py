"""生成 Base + RAG 与 LoRA + RAG 的同题配对报告。"""

from __future__ import annotations

import argparse
from pathlib import Path

from jobpilot_datasets.evaluation.comparison import RagModelComparison


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--bootstrap-samples", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=20260730)
    parser.add_argument("--review-size", type=int, default=40)
    args = parser.parse_args()

    report = RagModelComparison(
        bootstrap_samples=args.bootstrap_samples,
        seed=args.seed,
        review_size=args.review_size,
    ).run(args.cases, args.output_dir)
    print(
        f"配对分析完成：{report['paired_count']} 条，"
        f"检索一致 {report['retrieval_alignment']['matched']} 条",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
