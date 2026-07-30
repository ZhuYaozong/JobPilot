"""模型组合实验脚本入口。"""

from __future__ import annotations

import sys

from jobpilot_datasets.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["experiment", *sys.argv[1:]]))
