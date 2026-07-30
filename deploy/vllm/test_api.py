#!/usr/bin/env python3
"""测试 vLLM 的 OpenAI-compatible 模型列表与聊天补全接口。"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("VLLM_TEST_BASE_URL", "http://127.0.0.1:8000/v1"),
    )
    parser.add_argument("--api-key", default=os.environ.get("VLLM_API_KEY", ""))
    parser.add_argument(
        "--model",
        action="append",
        dest="models",
        help="可重复传入；默认测试 jobpilot-base 与 jobpilot-lora-v1",
    )
    parser.add_argument("--stream", action="store_true", help="额外测试 SSE 流式输出")
    return parser.parse_args()


def request_headers(api_key: str) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def request_json(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.load(response)


def test_chat(base_url: str, headers: dict[str, str], model: str) -> None:
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "你是 JobPilot 求职助手，请给出准确、简洁、可执行的建议。",
            },
            {
                "role": "user",
                "content": "请给出三条后端开发岗位简历项目描述的改写原则。",
            },
        ],
        "temperature": 0,
        "max_tokens": 256,
    }
    result = request_json(f"{base_url}/chat/completions", headers, payload)
    content = result["choices"][0]["message"]["content"]
    if not isinstance(content, str) or not content.strip():
        raise ValueError(f"模型 {model} 返回了空内容。")
    usage = result.get("usage", {})
    print(f"\n[{model}] 非流式调用通过")
    print(f"token 使用：{usage}")
    print(content.strip())


def test_stream(base_url: str, headers: dict[str, str], model: str) -> None:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "用一句话解释 STAR 法则。"}],
        "temperature": 0,
        "max_tokens": 128,
        "stream": True,
    }
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
    )
    chunks: list[str] = []
    with urllib.request.urlopen(request, timeout=180) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8").strip()
            if not line.startswith("data: "):
                continue
            data = line.removeprefix("data: ")
            if data == "[DONE]":
                break
            event = json.loads(data)
            chunks.append(event["choices"][0].get("delta", {}).get("content", ""))
    content = "".join(chunks).strip()
    if not content:
        raise ValueError(f"模型 {model} 的流式输出为空。")
    print(f"\n[{model}] 流式调用通过")
    print(content)


def main() -> None:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    headers = request_headers(args.api_key)
    models = args.models or ["jobpilot-base", "jobpilot-lora-v1"]

    try:
        model_list = request_json(f"{base_url}/models", headers)
        registered = {item["id"] for item in model_list.get("data", [])}
        print("服务已注册模型：", ", ".join(sorted(registered)))

        missing = set(models) - registered
        if missing:
            raise ValueError(f"以下待测模型未注册：{', '.join(sorted(missing))}")

        for model in models:
            test_chat(base_url, headers, model)
            if args.stream:
                test_stream(base_url, headers, model)
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        print(f"HTTP {error.code}：{body}", file=sys.stderr)
        raise SystemExit(1) from error
    except urllib.error.URLError as error:
        print(f"无法访问 vLLM 服务：{error.reason}", file=sys.stderr)
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
