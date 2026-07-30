#!/usr/bin/env python3
"""在不占用 GPU 的情况下检查 Base 模型和 LoRA adapter 是否可部署。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    """读取 JSON，并在路径错误时给出明确提示。"""
    if not path.is_file():
        raise FileNotFoundError(f"缺少文件：{path}")
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def sha256(path: Path) -> str:
    """流式计算大文件哈希，避免一次性读入内存。"""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def check_model_weights(model_path: Path) -> tuple[int, float]:
    """确认索引引用的每个权重分片都存在，并返回分片数与总大小。"""
    index_path = model_path / "model.safetensors.index.json"
    if index_path.is_file():
        index = load_json(index_path)
        weight_map = index.get("weight_map", {})
        shard_names = sorted(set(weight_map.values()))
        if not shard_names:
            raise ValueError(f"模型权重索引为空：{index_path}")
        shard_paths = [model_path / name for name in shard_names]
    else:
        shard_paths = sorted(model_path.glob("*.safetensors"))

    if not shard_paths:
        raise FileNotFoundError(f"Base 模型目录中没有 safetensors 权重：{model_path}")

    missing = [str(path) for path in shard_paths if not path.is_file()]
    if missing:
        raise FileNotFoundError("模型权重分片缺失：\n" + "\n".join(missing))

    empty = [str(path) for path in shard_paths if path.stat().st_size == 0]
    if empty:
        raise ValueError("模型权重分片为空：\n" + "\n".join(empty))

    total_gib = sum(path.stat().st_size for path in shard_paths) / 1024**3
    return len(shard_paths), round(total_gib, 2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model-path",
        default=os.environ.get("VLLM_MODEL_PATH"),
        help="Qwen2.5-7B-Instruct 本地目录",
    )
    parser.add_argument(
        "--adapter-path",
        default=os.environ.get("VLLM_ADAPTER_PATH"),
        help="LLaMA-Factory 导出的 LoRA adapter 目录",
    )
    parser.add_argument(
        "--max-model-len",
        type=int,
        default=int(os.environ.get("VLLM_MAX_MODEL_LEN", "16384")),
    )
    parser.add_argument(
        "--max-lora-rank",
        type=int,
        default=int(os.environ.get("VLLM_MAX_LORA_RANK", "16")),
    )
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.model_path or not args.adapter_path:
        raise ValueError("必须通过参数或环境变量提供模型与 adapter 路径。")

    model_path = Path(args.model_path).expanduser().resolve()
    adapter_path = Path(args.adapter_path).expanduser().resolve()
    model_config = load_json(model_path / "config.json")
    adapter_config = load_json(adapter_path / "adapter_config.json")
    model_shard_count, model_weight_gib = check_model_weights(model_path)

    architectures = model_config.get("architectures", [])
    if "Qwen2ForCausalLM" not in architectures:
        raise ValueError(f"模型架构不是预期的 Qwen2ForCausalLM：{architectures}")

    model_context = int(model_config.get("max_position_embeddings", 0))
    if model_context < args.max_model_len:
        raise ValueError(
            f"配置的上下文长度 {args.max_model_len} 超过模型上限 {model_context}。"
        )

    peft_type = str(adapter_config.get("peft_type", "")).upper()
    if peft_type != "LORA":
        raise ValueError(f"adapter 的 peft_type 不是 LORA：{peft_type or '缺失'}")

    adapter_rank = int(adapter_config.get("r", 0))
    if adapter_rank <= 0:
        raise ValueError(f"adapter rank 非法：{adapter_rank}")
    if adapter_rank > args.max_lora_rank:
        raise ValueError(
            f"adapter rank={adapter_rank} 超过 vLLM 上限 {args.max_lora_rank}。"
        )

    adapter_weights = adapter_path / "adapter_model.safetensors"
    if not adapter_weights.is_file() or adapter_weights.stat().st_size == 0:
        raise FileNotFoundError(f"LoRA 权重不存在或为空：{adapter_weights}")

    tokenizer_candidates = [
        model_path / "tokenizer.json",
        model_path / "tokenizer_config.json",
    ]
    if not all(path.is_file() for path in tokenizer_candidates):
        raise FileNotFoundError("Base 模型目录缺少 tokenizer 文件。")

    result = {
        "status": "passed",
        "model_path": str(model_path),
        "model_architecture": architectures,
        "model_context_limit": model_context,
        "requested_max_model_len": args.max_model_len,
        "model_weight_shards": model_shard_count,
        "model_weight_gib": model_weight_gib,
        "adapter_path": str(adapter_path),
        "adapter_rank": adapter_rank,
        "adapter_weight_mib": round(adapter_weights.stat().st_size / 1024**2, 2),
        "adapter_sha256": sha256(adapter_weights),
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("部署产物检查：通过")
        print(f"Base 架构：{', '.join(architectures)}")
        print(f"Base 权重：{model_shard_count} 个分片，共 {model_weight_gib} GiB")
        print(f"上下文：请求 {args.max_model_len} / 模型上限 {model_context}")
        print(f"LoRA rank：{adapter_rank}")
        print(f"LoRA 权重：{result['adapter_weight_mib']} MiB")
        print(f"LoRA SHA256：{result['adapter_sha256']}")


if __name__ == "__main__":
    main()
