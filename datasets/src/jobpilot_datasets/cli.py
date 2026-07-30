"""JobPilot 数据工程命令行入口。"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
from pathlib import Path

from jobpilot_datasets.config import AppConfig, load_config
from jobpilot_datasets.evaluation.runner import ExperimentRunner
from jobpilot_datasets.evaluation.sweep import RetrievalSweepRunner
from jobpilot_datasets.pipeline import DatasetPipeline, StageResult
from jobpilot_datasets.planning import (
    build_lora_evaluation_plan,
    build_rag_document_plan,
    build_sft_plan,
    plan_summary,
)
from jobpilot_datasets.providers.factory import create_provider
from jobpilot_datasets.quality import QualityInspector
from jobpilot_datasets.sources import (
    ExternalDocumentImporter,
    FileSystemDocumentSource,
)


DEFAULT_CONFIG = Path(__file__).resolve().parents[2] / "config.yaml"


def _add_config_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="配置文件路径",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jobpilot-datasets",
        description="JobPilot LoRA、RAG 与模型实验数据工程",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    plan_parser = subparsers.add_parser("plan", help="只展示确定性生产计划")
    _add_config_argument(plan_parser)

    generate_parser = subparsers.add_parser("generate", help="生成数据")
    _add_config_argument(generate_parser)
    generate_parser.add_argument(
        "--stage",
        choices=[
            "sft",
            "rag-documents",
            "rag-evaluation",
            "lora-evaluation",
            "all",
        ],
        default="all",
    )
    generate_parser.add_argument("--provider", help="覆盖 generation.provider")
    generate_parser.add_argument("--limit", type=int, help="仅处理前 N 个计划项")
    generate_parser.add_argument(
        "--resume",
        action="store_true",
        help="继续已有 checkpoint",
    )
    generate_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只展示计划，不创建 Provider 或写入文件",
    )

    import_parser = subparsers.add_parser(
        "import-docs",
        help="导入外部 Markdown/TXT/PDF/DOCX",
    )
    _add_config_argument(import_parser)
    import_parser.add_argument("source", type=Path)
    import_parser.add_argument("--recursive", action="store_true")

    quality_parser = subparsers.add_parser("quality", help="执行数据质量检查")
    _add_config_argument(quality_parser)
    quality_parser.add_argument(
        "--allow-missing",
        action="store_true",
        help="框架验收时允许正式数据文件尚未生成",
    )

    experiment_parser = subparsers.add_parser(
        "experiment",
        help="运行 Base/RAG/LoRA 对照实验",
    )
    _add_config_argument(experiment_parser)
    experiment_parser.add_argument("--limit", type=int)
    experiment_parser.add_argument(
        "--retrieval-only",
        action="store_true",
        help="只评估检索与重排，不创建或调用回答模型和 Judge",
    )

    sweep_parser = subparsers.add_parser(
        "retrieval-sweep",
        help="使用隔离调参集和验证集扫描 Hybrid + Rerank 参数",
    )
    _add_config_argument(sweep_parser)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
        if args.command == "plan":
            _print_plan(config)
            return 0
        if args.command == "generate":
            if args.limit is not None and args.limit <= 0:
                raise ValueError("--limit 必须大于 0")
            if args.stage == "all" and args.limit is not None:
                raise ValueError("--limit 不能与 --stage all 同时使用")
            if args.dry_run:
                _print_plan(config, stage=args.stage, limit=args.limit)
                return 0
            if args.provider:
                if args.provider not in config.providers:
                    raise ValueError(f"Provider 不存在: {args.provider}")
                config.generation.provider = args.provider
            return asyncio.run(_run_generation(config, args))
        if args.command == "import-docs":
            return _run_import(config, args)
        if args.command == "quality":
            report = QualityInspector(config).run(
                allow_missing=args.allow_missing,
            )
            print(
                json.dumps(
                    {
                        "passed": report.passed,
                        "counts": report.counts,
                        "issue_count": len(report.issues),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
            return 0 if report.passed else 1
        if args.command == "experiment":
            if args.limit is not None and args.limit <= 0:
                raise ValueError("--limit 必须大于 0")
            report = asyncio.run(
                ExperimentRunner(config).run(
                    limit=args.limit,
                    retrieval_only=args.retrieval_only,
                ),
            )
            print(
                json.dumps(
                    report.model_dump(mode="json"),
                    ensure_ascii=False,
                    indent=2,
                ),
            )
            return 0
        if args.command == "retrieval-sweep":
            report = asyncio.run(RetrievalSweepRunner(config).run())
            print(
                json.dumps(
                    {
                        "winner": report["winner"],
                        "baseline_validation": report["baseline_validation"],
                        "winner_delta_vs_baseline": report[
                            "winner_delta_vs_baseline"
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )
            return 0
    except (ValueError, RuntimeError, FileNotFoundError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2
    return 2


async def _run_generation(config: AppConfig, args: argparse.Namespace) -> int:
    provider = create_provider(config, config.generation.provider)
    pipeline = DatasetPipeline(
        config,
        provider,
        resume=args.resume,
        progress=lambda message: print(message, flush=True),
    )
    results: list[StageResult] = []
    try:
        if args.stage in {"sft", "all"}:
            results.append(await pipeline.generate_sft(limit=args.limit))
        if args.stage in {"rag-documents", "all"}:
            results.append(
                await pipeline.generate_rag_documents(limit=args.limit),
            )
        if args.stage in {"rag-evaluation", "all"}:
            results.append(
                await pipeline.generate_rag_evaluation(limit=args.limit),
            )
        if args.stage in {"lora-evaluation", "all"}:
            results.append(
                await pipeline.generate_lora_evaluation(limit=args.limit),
            )
    finally:
        await pipeline.close()

    for result in results:
        print(
            json.dumps(
                {
                    "stage": result.stage,
                    "planned": result.planned,
                    "accepted": result.accepted,
                    "completed": result.completed,
                    "outputs": result.output_files,
                },
                ensure_ascii=False,
            ),
        )
    if any(not result.completed for result in results):
        print(
            "当前为部分生成，只写入 checkpoint；正式输出将在该阶段全部完成后原子导出。",
        )
    return 0


def _run_import(config: AppConfig, args: argparse.Namespace) -> int:
    source = FileSystemDocumentSource(
        args.source,
        recursive=args.recursive,
        allowed_extensions=set(config.external_documents.allowed_extensions),
    )
    imported, warnings = ExternalDocumentImporter(config).import_source(source)
    print(f"成功导入 {len(imported)} 篇外部文档。")
    for warning in warnings:
        print(f"警告：{warning}")
    return 0


def _print_plan(
    config: AppConfig,
    *,
    stage: str = "all",
    limit: int | None = None,
) -> None:
    sft_plans = build_sft_plan(config)
    document_plans = build_rag_document_plan(config)
    lora_evaluation_plans = build_lora_evaluation_plan(config)
    sft_batch_size = config.generation.batch_size
    payload: dict[str, object] = {
        "seed": config.seed,
        "provider": config.generation.provider,
        "config_fingerprint": config.fingerprint,
    }
    if stage in {"sft", "all"}:
        selected = sft_plans[:limit] if limit is not None else sft_plans
        payload["sft"] = plan_summary(selected)
        payload["sft_estimated_minimum_calls"] = math.ceil(
            len(selected) / sft_batch_size,
        )
    if stage in {"rag-documents", "all"}:
        selected = (
            document_plans[:limit] if limit is not None else document_plans
        )
        payload["rag_documents"] = plan_summary(selected)
        payload["rag_documents_estimated_minimum_calls"] = math.ceil(
            len(selected) / config.rag_documents.batch_size,
        )
    if stage in {"rag-evaluation", "all"}:
        count = min(limit, config.rag_evaluation.total) if limit else (
            config.rag_evaluation.total
        )
        payload["rag_evaluation"] = {
            "total": count,
            "requires_document_manifest": True,
        }
        baseline_document_count = config.rag_documents.total
        per_document, remainder = divmod(count, baseline_document_count)
        payload["rag_evaluation_estimated_calls_for_generated_documents"] = sum(
            math.ceil(
                (per_document + (1 if index < remainder else 0))
                / config.rag_evaluation.batch_size,
            )
            for index in range(baseline_document_count)
        )
    if stage in {"lora-evaluation", "all"}:
        selected = (
            lora_evaluation_plans[:limit]
            if limit is not None
            else lora_evaluation_plans
        )
        payload["lora_evaluation"] = plan_summary(selected)
        payload["lora_evaluation_estimated_minimum_calls"] = math.ceil(
            len(selected) / config.lora_evaluation.batch_size,
        )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
