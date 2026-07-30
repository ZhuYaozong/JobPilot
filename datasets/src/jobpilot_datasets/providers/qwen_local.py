"""通过 transformers 直接调用本地 Qwen 模型。"""

from __future__ import annotations

import asyncio
from typing import Any

from jobpilot_datasets.config import ProviderConfig
from jobpilot_datasets.providers.base import (
    GenerationRequest,
    ProviderConfigurationError,
    ProviderRequestError,
    ProviderUsageStats,
)


class QwenLocalProvider:
    """延迟加载模型，避免仅运行 plan/quality 时导入 torch。"""

    def __init__(self, config: ProviderConfig) -> None:
        if not config.model.strip():
            raise ProviderConfigurationError("本地 Qwen Provider 缺少模型路径")
        self.config = config
        self._tokenizer: Any = None
        self._model: Any = None
        self._torch: Any = None
        self._load_lock = asyncio.Lock()
        # GPU 模型默认串行调用；更高并发应交给 vLLM 等服务端。
        self._semaphore = asyncio.Semaphore(config.concurrency)
        self._usage = ProviderUsageStats()

    async def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        async with self._load_lock:
            if self._model is not None:
                return
            try:
                import torch
                from transformers import AutoModelForCausalLM, AutoTokenizer
            except ImportError as exc:
                raise ProviderConfigurationError(
                    "请先安装本地模型依赖：uv sync --extra qwen",
                ) from exc

            dtype: Any = "auto"
            if self.config.dtype != "auto":
                dtype = getattr(torch, self.config.dtype, None)
                if dtype is None:
                    raise ProviderConfigurationError(
                        f"不支持的 torch dtype: {self.config.dtype}",
                    )

            def load() -> tuple[Any, Any]:
                tokenizer = AutoTokenizer.from_pretrained(
                    self.config.model,
                    trust_remote_code=self.config.trust_remote_code,
                )
                device_map = (
                    self.config.device
                    if self.config.device
                    in {"auto", "balanced", "balanced_low_0", "sequential"}
                    else None
                )
                model = AutoModelForCausalLM.from_pretrained(
                    self.config.model,
                    torch_dtype=dtype,
                    device_map=device_map,
                    trust_remote_code=self.config.trust_remote_code,
                )
                if device_map is None:
                    model.to(self.config.device)
                model.eval()
                return tokenizer, model

            self._tokenizer, self._model = await asyncio.to_thread(load)
            self._torch = torch

    async def generate(self, request: GenerationRequest) -> str:
        await self._ensure_loaded()
        async with self._semaphore:
            self._usage.request_attempts += 1
            try:
                content, prompt_tokens, completion_tokens = await asyncio.to_thread(
                    self._generate_sync,
                    request,
                )
                self._usage.successful_responses += 1
                self._usage.usage_reported_responses += 1
                self._usage.prompt_tokens += prompt_tokens
                self._usage.completion_tokens += completion_tokens
                self._usage.total_tokens += prompt_tokens + completion_tokens
                return content
            except Exception as exc:
                self._usage.failed_attempts += 1
                raise ProviderRequestError("本地 Qwen 推理失败") from exc

    def _generate_sync(
        self,
        request: GenerationRequest,
    ) -> tuple[str, int, int]:
        messages = [
            {"role": "system", "content": request.system_prompt},
            {"role": "user", "content": request.user_prompt},
        ]
        prompt = self._tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = self._tokenizer([prompt], return_tensors="pt")
        device = next(self._model.parameters()).device
        inputs = {key: value.to(device) for key, value in inputs.items()}

        self._torch.manual_seed(request.seed)
        if self._torch.cuda.is_available():
            self._torch.cuda.manual_seed_all(request.seed)

        temperature = (
            self.config.temperature
            if request.temperature is None
            else request.temperature
        )
        generation_args: dict[str, Any] = {
            **inputs,
            "max_new_tokens": request.max_tokens or self.config.max_tokens,
            "do_sample": temperature > 0,
        }
        if temperature > 0:
            generation_args.update({"temperature": temperature, "top_p": 0.9})

        generated = self._model.generate(**generation_args)
        prompt_length = inputs["input_ids"].shape[1]
        new_tokens = generated[0][prompt_length:]
        content = self._tokenizer.decode(new_tokens, skip_special_tokens=True)
        if not content.strip():
            raise ValueError("本地模型返回空内容")
        return content, prompt_length, int(new_tokens.shape[0])

    async def close(self) -> None:
        # Python 进程退出时释放模型；这里清引用便于长生命周期 CLI 切换模型。
        self._model = None
        self._tokenizer = None
        if self._torch is not None and self._torch.cuda.is_available():
            self._torch.cuda.empty_cache()

    @property
    def usage_stats(self) -> dict[str, int]:
        return self._usage.snapshot()
