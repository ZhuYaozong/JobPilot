"""运行 Base/LoRA Agent + Hybrid RAG 的成对正式评测。"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import json
import re
import time
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.agent.tool_catalog import ToolCatalog
from app.agent.tools import TOOL_REGISTRY
from app.core.config import settings
from app.eval.agent_pair_cli import (
    _model_override,
    _read_json,
    _read_jsonl,
    _resolve_config_path,
    _sha256_file,
    _write_json,
    append_jsonl,
    safe_model_name,
)
from app.eval.agent_rag_fixture import (
    FixtureSnapshot,
    load_document_specs,
    load_fixture_snapshot,
    prepare_fixture,
)
from app.eval.runner import _collect_trace
from app.llm.client import LLMClient
from app.llm.embedding_client import EmbeddingClient
from app.models.user import User
from app.rag.reranker import HttpReranker
from app.rag.types import RetrievalHit
from app.schemas.assistant import AssistantRunRequest, ContextSelection
from app.services.assistant_service import run_assistant_turn


REQUIRED_FIELDS = {
    "question",
    "answer",
    "source_document",
    "supporting_excerpt",
}


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    config_path = Path(args.config).resolve()
    config = _read_json(config_path)
    records, data_preflight = load_rag_records(config, config_path=config_path)

    if args.prepare_kb or args.rebuild_kb:
        fixture = asyncio.run(prepare_fixture(
            config,
            config_path=config_path,
            rebuild=bool(args.rebuild_kb),
        ))
        print(json.dumps(fixture.to_dict(), ensure_ascii=False, indent=2))
        if args.prepare_only:
            return 0
    else:
        fixture = asyncio.run(load_fixture_snapshot(config, config_path=config_path))

    selected = records[:args.limit] if args.limit is not None else records
    if not selected:
        raise ValueError("没有选中任何评测记录")
    models = args.models or list(config["models"])
    if len(models) != 2:
        raise ValueError("成对评测要求恰好两个模型")

    output_root = _resolve_config_path(config_path, str(config["output_dir"]))
    run_dir = output_root / args.run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    with strict_rag_settings():
        service_preflight = asyncio.run(probe_services(models))
        metadata = {
            "run_name": args.run_name,
            "models": models,
            "selected_count": len(selected),
            "selected_case_ids": [row["case_id"] for row in selected],
            "dataset_sha256": data_preflight["dataset_sha256"],
            "document_set_sha256": fixture.document_set_sha256,
            "fixture": fixture.to_dict(),
            "rag": rag_config_snapshot(),
            "tool_policy": "仅开放 search_knowledge；respond_directly 仍可由 Agent 选择",
            "timeout_seconds": float(config.get("timeout_seconds", 120)),
            "concurrency": int(config.get("concurrency", 1)),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        _write_json(run_dir / "preflight.json", {
            **data_preflight,
            "fixture": fixture.to_dict(),
            "services": service_preflight,
            "rag": rag_config_snapshot(),
            "status": "passed",
        })
        _write_json(run_dir / "run_metadata.json", metadata)

        for model in models:
            output_path = run_dir / f"{safe_model_name(model)}.jsonl"
            finished = latest_results_by_case(output_path)
            pending = [
                row for row in selected
                if should_run_case(
                    finished.get(row["case_id"]),
                    retry_failed=bool(args.retry_failed),
                    retry_error_classes=frozenset(args.retry_error_classes or []),
                )
            ]
            print(f"[{model}] 已完成 {len(selected) - len(pending)}/{len(selected)}")
            with _model_override(model):
                asyncio.run(run_model_batch(
                    pending,
                    model=model,
                    fixture=fixture,
                    output_path=output_path,
                    timeout_seconds=float(config.get("timeout_seconds", 120)),
                    concurrency=int(config.get("concurrency", 1)),
                ))

    print(f"Agent + RAG 配对运行完成: {run_dir}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-name", default="full")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--model", action="append", dest="models")
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument(
        "--retry-error-class",
        action="append",
        dest="retry_error_classes",
        help="与--retry-failed合用，只重跑指定Agent错误类型；可重复指定",
    )
    parser.add_argument("--prepare-kb", action="store_true")
    parser.add_argument("--rebuild-kb", action="store_true")
    parser.add_argument("--prepare-only", action="store_true")
    return parser


def load_rag_records(
    config: dict[str, Any],
    *,
    config_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """读取冻结RAG问题，并验证数量、字段、来源和文件哈希。"""
    evaluation_path = _resolve_config_path(config_path, str(config["evaluation_path"]))
    rows = _read_jsonl(evaluation_path)
    expected_count = int(config.get("expected_count", 200))
    if len(rows) != expected_count:
        raise ValueError(f"RAG评测集应为 {expected_count} 条，实际 {len(rows)} 条")
    expected_sha = str(config["dataset_sha256"]).lower()
    actual_sha = _sha256_file(evaluation_path).lower()
    if actual_sha != expected_sha:
        raise ValueError(f"RAG评测集SHA256不一致: {actual_sha} != {expected_sha}")

    document_sources = {
        spec.source_document
        for spec in load_document_specs(config, config_path=config_path)
    }
    records: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        missing = REQUIRED_FIELDS - set(row)
        if missing:
            raise ValueError(f"RAG记录 {index} 缺少字段: {sorted(missing)}")
        normalized = {field: str(row[field]).strip() for field in REQUIRED_FIELDS}
        if not all(normalized.values()):
            raise ValueError(f"RAG记录 {index} 存在空字段")
        if normalized["source_document"] not in document_sources:
            raise ValueError(
                f"RAG记录 {index} 来源不存在: {normalized['source_document']}",
            )
        records.append({
            "case_id": f"rag-{index:04d}",
            "index": index,
            **normalized,
            "record_sha256": hashlib.sha256(
                json.dumps(row, ensure_ascii=False, sort_keys=True).encode("utf-8"),
            ).hexdigest(),
        })
    return records, {
        "evaluation_path": str(evaluation_path),
        "dataset_sha256": actual_sha,
        "record_count": len(records),
        "unique_questions": len({row["question"] for row in records}),
        "unique_source_documents": len({row["source_document"] for row in records}),
    }


async def run_model_batch(
    records: list[dict[str, Any]],
    *,
    model: str,
    fixture: FixtureSnapshot,
    output_path: Path,
    timeout_seconds: float,
    concurrency: int,
) -> None:
    """有限并发运行一个模型，主协程按完成顺序原子追加结果。"""
    if concurrency <= 0:
        raise ValueError("concurrency必须大于0")
    semaphore = asyncio.Semaphore(concurrency)

    async def _guarded(record: dict[str, Any]) -> dict[str, Any]:
        async with semaphore:
            return await run_agent_rag_case(
                record,
                model=model,
                fixture=fixture,
                timeout_seconds=timeout_seconds,
            )

    tasks = [asyncio.create_task(_guarded(record)) for record in records]
    for position, task in enumerate(asyncio.as_completed(tasks), start=1):
        row = await task
        append_jsonl(output_path, row)
        tools = ",".join(
            str(name)
            for name in (row.get("agent") or {}).get("tool_sequence", [])
            if name
        ) or "直答"
        print(
            f"[{model}] {position}/{len(records)} {row['case_id']} "
            f"[{row['status']}] {row['latency_seconds']:.2f}s tools={tools}",
            flush=True,
        )


async def run_agent_rag_case(
    source: dict[str, Any],
    *,
    model: str,
    fixture: FixtureSnapshot,
    timeout_seconds: float,
) -> dict[str, Any]:
    """用固定用户/知识库执行一个真实Agent turn，并抽取完整轨迹。"""
    started = time.perf_counter()
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    trace = None
    framework_error: str | None = None
    try:
        async with AsyncSession(engine, expire_on_commit=False) as db:
            user = (await db.execute(
                select(User).where(User.id == fixture.user_id),
            )).scalar_one_or_none()
            if user is None or not user.is_test_user:
                raise ValueError("评测用户不存在或不再是测试用户")
            payload = AssistantRunRequest(
                conversation_id=None,
                content=(
                    "请仅根据当前选中知识库中的资料回答；如果资料不足，请明确说明。\n\n"
                    f"问题：{source['question']}"
                ),
                context=ContextSelection(
                    knowledge_base_id=fixture.knowledge_base_id,
                ),
            )
            catalog = search_only_catalog()
            try:
                response = await asyncio.wait_for(
                    run_assistant_turn(
                        db,
                        user,
                        payload,
                        llm_client=LLMClient(),
                        tool_catalog=catalog,
                    ),
                    timeout=timeout_seconds,
                )
                trace = await _collect_trace(
                    db,
                    response.conversation_id,
                    response.agent_run.id,
                )
            except asyncio.TimeoutError:
                framework_error = f"case超时(>{timeout_seconds}s)"
            except Exception as exc:  # noqa: BLE001 — 单条失败不能中断整批
                framework_error = f"{type(exc).__name__}: {exc}"
    finally:
        await engine.dispose()

    duration = round(time.perf_counter() - started, 4)
    tool_calls = trace.tool_calls if trace else []
    search_calls = [
        call for call in tool_calls
        if call.get("tool_name") == "search_knowledge"
    ]
    retrieved_hits = extract_retrieved_hits(search_calls)
    prediction = trace.final_text if trace and trace.final_text else ""
    workflow_succeeded = bool(
        trace and trace.agent_run_status == "succeeded" and prediction,
    )
    correct_kb_calls = sum(
        int((call.get("arguments") or {}).get("knowledge_base_id") or -1)
        == fixture.knowledge_base_id
        for call in search_calls
    )
    successful_search_calls = sum(
        search_call_succeeded(call)
        for call in search_calls
    )
    route_passed = bool(
        workflow_succeeded
        and len(search_calls) == 1
        and successful_search_calls == 1
        and correct_kb_calls == 1
    )
    return {
        "status": "success" if workflow_succeeded else "failed",
        "case_id": source["case_id"],
        "index": source["index"],
        "record_sha256": source["record_sha256"],
        "model": model,
        "question": source["question"],
        "reference_answer": source["answer"],
        "source_document": source["source_document"],
        "supporting_excerpt": source["supporting_excerpt"],
        "prediction": prediction,
        "latency_seconds": duration,
        "case_passed": route_passed,
        "framework_error": framework_error,
        "agent": {
            "run_status": trace.agent_run_status if trace else None,
            "error_class": trace.agent_run_error_class if trace else None,
            "error_detail": trace.agent_run_error_detail if trace else None,
            "conversation_id": trace.conversation_id if trace else None,
            "agent_run_id": trace.agent_run_id if trace else None,
            "tool_sequence": [call.get("tool_name") for call in tool_calls],
            "tool_calls": tool_calls,
        },
        "rag": {
            "expected_knowledge_base_id": fixture.knowledge_base_id,
            "search_call_count": len(search_calls),
            "successful_search_call_count": successful_search_calls,
            "correct_knowledge_base_call_count": correct_kb_calls,
            "direct_route": len(search_calls) == 0,
            "retrieved_sources": [hit.get("document_title") for hit in retrieved_hits],
            "retrieved_hits": retrieved_hits,
        },
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }


def search_only_catalog() -> ToolCatalog:
    """只向Agent暴露只读RAG工具，隔离其他业务工具干扰。"""
    return ToolCatalog.local_only(
        exclude_names=set(TOOL_REGISTRY) - {"search_knowledge"},
    )


def extract_retrieved_hits(search_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按工具调用顺序摊平命中，兼容Adapter落库后的data展平形状。"""
    hits: list[dict[str, Any]] = []
    for call in search_calls:
        result = call.get("result") or {}
        if not isinstance(result, dict):
            continue
        nested = result.get("data")
        data = nested if isinstance(nested, dict) else result
        raw_hits = data.get("hits") if isinstance(data, dict) else None
        if isinstance(raw_hits, list):
            hits.extend(hit for hit in raw_hits if isinstance(hit, dict))
    return hits


def search_call_succeeded(call: dict[str, Any]) -> bool:
    """ToolCallLog的success已代表ok=true；未展平的测试形状再检查ok。"""
    if call.get("status") != "success":
        return False
    result = call.get("result")
    if not isinstance(result, dict):
        return False
    return result.get("ok", True) is not False


def latest_results_by_case(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    return {
        str(row["case_id"]): row
        for row in _read_jsonl(path)
        if row.get("case_id")
    }


def should_run_case(
    previous: dict[str, Any] | None,
    *,
    retry_failed: bool,
    retry_error_classes: frozenset[str],
) -> bool:
    """决定case是否待运行；错误类型过滤避免重试掩盖真实模型失败。"""
    if previous is None:
        return True
    if not retry_failed or previous.get("status") == "success":
        return False
    if not retry_error_classes:
        return True
    error_class = str((previous.get("agent") or {}).get("error_class") or "")
    return error_class in retry_error_classes


async def probe_services(models: list[str]) -> dict[str, Any]:
    """在正式运行前真实探测生成、Embedding和Reranker三个接口。"""
    if not settings.llm_base_url or not settings.llm_api_key:
        raise ValueError("LLM服务未配置")
    headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            f"{settings.llm_base_url.rstrip('/')}/models",
            headers=headers,
        )
        response.raise_for_status()
        body = response.json()
    available_models = sorted(
        str(item.get("id"))
        for item in body.get("data", [])
        if isinstance(item, dict) and item.get("id")
    )
    missing = sorted(set(models) - set(available_models))
    if missing:
        raise ValueError(f"LLM服务缺少模型别名: {missing}; available={available_models}")

    vectors = await EmbeddingClient().embed(["JobPilot Agent RAG 健康检查"])
    if len(vectors) != 1 or len(vectors[0]) != 1024:
        raise ValueError("Embedding服务没有返回单个1024维向量")
    reranker = HttpReranker(
        base_url=settings.reranker_base_url,
        api_key=settings.reranker_api_key,
        model_name=settings.reranker_model_name,
        timeout_seconds=settings.reranker_timeout_seconds,
    )
    probe_hit = RetrievalHit(
        chunk_id=0,
        document_id=0,
        document_title="health-check",
        knowledge_base_id=0,
        source_type="manual",
        chunk_index=0,
        char_start=0,
        char_end=8,
        content="混合检索与重排",
        score=1.0,
        relevance=1.0,
        distance=0.0,
        rank=1,
        source="probe",
    )
    reranked = await reranker.rerank("如何进行混合检索", [probe_hit], top_k=1)
    if len(reranked) != 1:
        raise ValueError("Reranker服务健康检查未返回结果")
    return {
        "llm_models": available_models,
        "requested_models": models,
        "embedding_dimensions": len(vectors[0]),
        "reranker_result_count": len(reranked),
    }


def rag_config_snapshot() -> dict[str, Any]:
    return {
        "strategy": settings.rag_strategy,
        "candidate_multiplier": settings.rag_candidate_multiplier,
        "vector_weight": settings.rag_vector_weight,
        "bm25_weight": settings.rag_bm25_weight,
        "rrf_k": settings.rag_hybrid_rrf_k,
        "vector_fail_open": settings.rag_hybrid_vector_fail_open,
        "reranker_enabled": settings.rag_reranker_enabled,
        "reranker_fail_open": settings.rag_reranker_fail_open,
        "embedding_model": settings.embedding_model_name,
        "embedding_dimensions": settings.embedding_dimensions,
        "reranker_model": settings.reranker_model_name,
    }


@contextlib.contextmanager
def strict_rag_settings() -> Iterator[None]:
    """实验进程内关闭静默降级，确保每条成功样本确实用了Hybrid+Rerank。"""
    if settings.rag_strategy != "hybrid":
        raise ValueError(f"正式评测要求RAG_STRATEGY=hybrid，实际 {settings.rag_strategy}")
    if not settings.rag_reranker_enabled:
        raise ValueError("正式评测要求RAG_RERANKER_ENABLED=true")
    previous_vector = settings.rag_hybrid_vector_fail_open
    previous_reranker = settings.rag_reranker_fail_open
    settings.rag_hybrid_vector_fail_open = False
    settings.rag_reranker_fail_open = False
    try:
        yield
    finally:
        settings.rag_hybrid_vector_fail_open = previous_vector
        settings.rag_reranker_fail_open = previous_reranker


if __name__ == "__main__":
    raise SystemExit(main())
