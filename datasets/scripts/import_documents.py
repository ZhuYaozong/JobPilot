"""外部文档导入脚本入口。"""

from __future__ import annotations

import sys

from jobpilot_datasets.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["import-docs", *sys.argv[1:]]))
