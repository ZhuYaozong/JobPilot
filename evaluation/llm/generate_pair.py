#!/usr/bin/env python3
"""通过同一 vLLM 服务对 Base 与 LoRA 执行可恢复的配对生成。"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REQUIRED_DATASET_FIELDS = {"instruction", "input", "output"}
REQUIRED_MANIFEST_FIELDS = {"plan_id", "task_type", "record_sha256"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="评测 JSON 配置")
    parser.add_argument("--run-name", default="full", help="输出子目录，如 smoke/full")
    parser.add_argument("--limit", type=int, default=None, help="仅评测前 N 条")
    parser.add_argument(
        "--model",
        action="append",
        dest="models",
        help="覆盖配置中的模型，可重复传入",
    )
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"{path}:{line_number} JSON 无效") from error
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} 必须是 JSON object")
            records.append(value)
    return records


def write_json(path: Path, value: Any) -> None:
    """先写临时文件再替换，避免中断后留下半截 JSON。"""
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(value, file, ensure_ascii=False, indent=2)
        file.write("\n")
    temporary.replace(path)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def prompt_fingerprint(record: dict[str, Any]) -> str:
    """只对输入做指纹，检查独立评测集是否与其他 split 完全重复。"""
    normalized = {
        "instruction": str(record.get("instruction", "")).strip(),
        "input": str(record.get("input", "")).strip(),
    }
    payload = json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_data(config: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    dataset_path = Path(config["dataset_path"]).resolve()
    manifest_path = Path(config["manifest_path"]).resolve()
    dataset = read_jsonl(dataset_path)
    manifest = read_jsonl(manifest_path)

    if len(dataset) != len(manifest):
        raise ValueError(
            f"评测集 {len(dataset)} 条，但 manifest {len(manifest)} 条，无法配对。"
        )

    plan_ids: set[str] = set()
    items: list[dict[str, Any]] = []
    for index, (record, metadata) in enumerate(zip(dataset, manifest, strict=True)):
        missing_record = REQUIRED_DATASET_FIELDS - record.keys()
        missing_manifest = REQUIRED_MANIFEST_FIELDS - metadata.keys()
        if missing_record:
            raise ValueError(f"评测记录 {index} 缺少字段：{sorted(missing_record)}")
        if missing_manifest:
            raise ValueError(f"manifest {index} 缺少字段：{sorted(missing_manifest)}")
        if not str(record["instruction"]).strip() or not str(record["output"]).strip():
            raise ValueError(f"评测记录 {index} 的 instruction/output 不能为空")

        plan_id = str(metadata["plan_id"])
        if plan_id in plan_ids:
            raise ValueError(f"manifest 出现重复 plan_id：{plan_id}")
        plan_ids.add(plan_id)
        items.append(
            {
                "index": index,
                "plan_id": plan_id,
                "task_type": str(metadata["task_type"]),
                "record_sha256": str(metadata["record_sha256"]),
                "record": record,
                "prompt_sha256": prompt_fingerprint(record),
            }
        )

    evaluation_fingerprints = {item["prompt_sha256"] for item in items}
    leakage: dict[str, int] = {}
    for raw_path in config.get("leakage_check_paths", []):
        split_path = Path(raw_path).resolve()
        split_fingerprints = {prompt_fingerprint(record) for record in read_jsonl(split_path)}
        leakage[split_path.name] = len(evaluation_fingerprints & split_fingerprints)

    preflight = {
        "status": "passed",
        "dataset_path": str(dataset_path),
        "dataset_sha256": file_sha256(dataset_path),
        "manifest_path": str(manifest_path),
        "manifest_sha256": file_sha256(manifest_path),
        "record_count": len(items),
        "unique_plan_ids": len(plan_ids),
        "exact_prompt_leakage": leakage,
    }
    return items, preflight


def safe_model_name(model: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", model)


def load_completed(path: Path) -> set[str]:
    """仅成功记录参与断点续跑；失败记录会在下次执行时重试。"""
    if not path.is_file():
        return set()
    completed: set[str] = set()
    for record in read_jsonl(path):
        if record.get("status") == "success":
            completed.add(str(record["plan_id"]))
    return completed


def user_content(record: dict[str, Any]) -> str:
    instruction = str(record["instruction"]).strip()
    query = str(record.get("input", "")).strip()
    return instruction if not query else f"{instruction}\n{query}"


def post_chat(
    *,
    endpoint: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout_seconds: float,
) -> dict[str, Any]:
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return json.load(response)


def generate_one(
    *,
    item: dict[str, Any],
    model: str,
    config: dict[str, Any],
    headers: dict[str, str],
) -> dict[str, Any]:
    record = item["record"]
    content = user_content(record)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": config["system_prompt"]},
            {"role": "user", "content": content},
        ],
        "temperature": config["temperature"],
        "max_tokens": config["max_tokens"],
        "seed": config["seed"],
    }
    request_sha256 = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()

    started_at = time.perf_counter()
    last_error = ""
    for attempt in range(1, int(config["max_retries"]) + 1):
        try:
            response = post_chat(
                endpoint=f"{str(config['api_base_url']).rstrip('/')}/chat/completions",
                headers=headers,
                payload=payload,
                timeout_seconds=float(config["timeout_seconds"]),
            )
            prediction = response["choices"][0]["message"]["content"]
            if not isinstance(prediction, str) or not prediction.strip():
                raise ValueError("模型返回空文本")
            return {
                "status": "success",
                "plan_id": item["plan_id"],
                "index": item["index"],
                "task_type": item["task_type"],
                "record_sha256": item["record_sha256"],
                "prompt_sha256": item["prompt_sha256"],
                "request_sha256": request_sha256,
                "model": model,
                "instruction": record["instruction"],
                "input": record.get("input", ""),
                "reference": record["output"],
                "prediction": prediction.strip(),
                "usage": response.get("usage", {}),
                "latency_seconds": round(time.perf_counter() - started_at, 4),
                "attempts": attempt,
                "response_id": response.get("id"),
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")[:2000]
            last_error = f"HTTP {error.code}: {body}"
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as error:
            last_error = f"{type(error).__name__}: {error}"

        if attempt < int(config["max_retries"]):
            time.sleep(float(config["retry_backoff_seconds"]) * (2 ** (attempt - 1)))

    return {
        "status": "error",
        "plan_id": item["plan_id"],
        "index": item["index"],
        "task_type": item["task_type"],
        "record_sha256": item["record_sha256"],
        "prompt_sha256": item["prompt_sha256"],
        "request_sha256": request_sha256,
        "model": model,
        "error": last_error,
        "latency_seconds": round(time.perf_counter() - started_at, 4),
        "attempts": int(config["max_retries"]),
        "finished_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> None:
    args = parse_args()
    config_path = Path(args.config).resolve()
    config = read_json(config_path)
    models = args.models or list(config["models"])
    if len(models) < 1 or len(set(models)) != len(models):
        raise ValueError("模型列表不能为空且不能重复")
    if int(config["concurrency"]) < 1:
        raise ValueError("concurrency 必须大于 0")

    items, preflight = validate_data(config)
    if args.limit is not None:
        if args.limit <= 0:
            raise ValueError("--limit 必须大于 0")
        items = items[: args.limit]

    output_dir = Path(config["output_dir"]).resolve() / args.run_name
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "preflight.json", preflight)
    write_json(
        output_dir / "run_metadata.json",
        {
            "config_path": str(config_path),
            "run_name": args.run_name,
            "models": models,
            "selected_count": len(items),
            "selected_plan_ids": [item["plan_id"] for item in items],
            "generation": {
                "system_prompt": config["system_prompt"],
                "temperature": config["temperature"],
                "max_tokens": config["max_tokens"],
                "seed": config["seed"],
                "concurrency": config["concurrency"],
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    api_key = os.environ.get(str(config.get("api_key_env", "")), "")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    output_paths = {
        model: output_dir / f"{safe_model_name(model)}.jsonl" for model in models
    }
    completed = {model: load_completed(path) for model, path in output_paths.items()}
    jobs = [
        (item, model)
        for item in items
        for model in models
        if item["plan_id"] not in completed[model]
    ]

    print("数据预检：通过")
    print(f"独立评测记录：{preflight['record_count']} 条，本次选择：{len(items)} 条")
    print(f"精确 Prompt 泄漏：{preflight['exact_prompt_leakage']}")
    print(f"待执行请求：{len(jobs)}；并发：{config['concurrency']}")
    if not jobs:
        print("所有成功记录均已存在，无需重复生成。")
        return

    handles = {
        model: path.open("a", encoding="utf-8", newline="\n")
        for model, path in output_paths.items()
    }
    success_count = 0
    error_count = 0
    try:
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=int(config["concurrency"])
        ) as executor:
            futures = {
                executor.submit(
                    generate_one,
                    item=item,
                    model=model,
                    config=config,
                    headers=headers,
                ): (item, model)
                for item, model in jobs
            }
            for completed_count, future in enumerate(
                concurrent.futures.as_completed(futures), start=1
            ):
                _, model = futures[future]
                result = future.result()
                json.dump(result, handles[model], ensure_ascii=False)
                handles[model].write("\n")
                handles[model].flush()
                if result["status"] == "success":
                    success_count += 1
                else:
                    error_count += 1
                if completed_count % 10 == 0 or result["status"] != "success":
                    print(
                        f"进度 {completed_count}/{len(jobs)}；"
                        f"成功 {success_count}；失败 {error_count}",
                        flush=True,
                    )
    finally:
        for handle in handles.values():
            handle.close()

    print(f"生成完成：成功 {success_count}，失败 {error_count}")
    if error_count:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
