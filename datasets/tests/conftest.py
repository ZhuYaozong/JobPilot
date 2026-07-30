"""测试公共配置与确定性模型替身。"""

from __future__ import annotations

import json
import hashlib
import re
from pathlib import Path

import pytest

from jobpilot_datasets.config import AppConfig, load_config
from jobpilot_datasets.providers.base import GenerationRequest
from jobpilot_datasets.evaluation.retrieval import SearchResult


DATASETS_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def test_config(tmp_path: Path) -> AppConfig:
    config = load_config(DATASETS_ROOT / "config.yaml")
    config.paths.output_root = tmp_path
    config.paths.prompts_dir = DATASETS_ROOT / "prompts"
    config.paths.schemas_dir = DATASETS_ROOT / "schemas"
    config.lora.splits = {"train": 6, "val": 6, "test": 6}
    config.rag_documents.total = 1
    config.rag_documents.batch_size = 1
    config.rag_documents.min_chars = 300
    config.rag_documents.max_chars = 1200
    config.rag_evaluation.total = 2
    config.rag_evaluation.batch_size = 2
    config.lora_evaluation.total = 2
    config.lora_evaluation.batch_size = 2
    config.generation.batch_size = 6
    return config


class DeterministicProvider:
    """根据 Prompt 中的 plan_id 生成满足门禁的固定内容。"""

    def __init__(self, answer: str | None = None) -> None:
        self.requests: list[GenerationRequest] = []
        self.answer = answer
        self.closed = False

    async def generate(self, request: GenerationRequest) -> str:
        self.requests.append(request)
        if self.answer is not None:
            return self.answer
        if (
            "面试官和训练数据工程师" in request.system_prompt
            or "评测设计专家" in request.system_prompt
        ):
            plan_ids = sorted(
                set(
                    re.findall(
                        r"(?:sft-[a-z]+-\d{2}-\d{4}|loraeval-\d{2}-\d{4})",
                        request.user_prompt,
                    ),
                ),
            )
            output = (
                "我会先把需求拆成输入校验、核心服务和结果持久化三个模块，并为接口设置"
                "三十秒超时、两次指数退避重试和幂等键。上线前用固定样本做回归，监控"
                "P95延迟、失败率与单次调用成本；出现异常时保留原始响应并降级到规则方案。"
                "这种设计增加少量存储和监控成本，但换来可回放、可定位和可灰度回滚的能力。"
            )
            return json.dumps(
                {
                    "items": [
                        {
                            "plan_id": plan_id,
                            "instruction": (
                                "请结合真实项目说明标识为 "
                                f"{hashlib.sha256(plan_id.encode()).hexdigest()[:24]} "
                                "的场景应如何设计并处理失败？"
                            ),
                            "input": "假设服务需要支持多用户并发，并且上游模型偶发超时。",
                            "output": output,
                        }
                        for plan_id in plan_ids
                    ],
                },
                ensure_ascii=False,
            )
        if "AI 应用工程技术文档作者" in request.system_prompt:
            plan_ids = sorted(set(re.findall(r"ragdoc-\d{2}-\d{3}", request.user_prompt)))
            excerpt = "工程实现采用接口模块化，并配置超时重试、监控指标和回滚流程。"
            body = (
                "该能力用于把模型行为转化为可维护的工程服务。"
                f"{excerpt}"
                "请求进入服务后先执行字段校验和权限检查，再进入核心处理模块；"
                "结果写入带版本号的存储，并记录请求标识、耗时和错误分类。"
                "团队使用固定测试集观察准确率、P95延迟和失败率，通过灰度流量比较新旧版本。"
                "发生依赖超时会执行有限次数的指数退避，仍失败则返回可识别错误并触发降级。"
                "方案在开发复杂度与稳定性之间做取舍，关键链路优先保证可观测和可回放。"
            )
            markdown = (
                "# 工程化知识文档\n\n"
                "## 概念\n\n"
                f"{body}\n\n"
                "## 原理\n\n"
                f"{body}\n\n"
                "## 实践案例\n\n"
                f"{body}\n"
            )
            return json.dumps(
                {
                    "items": [
                        {
                            "plan_id": plan_id,
                            "title": "工程化知识文档",
                            "markdown": markdown,
                        }
                        for plan_id in plan_ids
                    ],
                },
                ensure_ascii=False,
            )
        if "RAG 评测集设计专家" in request.system_prompt:
            plan_ids = sorted(set(re.findall(r"rageval-[a-f0-9]{10}-\d{3}", request.user_prompt)))
            excerpt = "工程实现采用接口模块化，并配置超时重试、监控指标和回滚流程。"
            return json.dumps(
                {
                    "items": [
                        {
                            "plan_id": plan_id,
                            "question": (
                                "对于证据标识 "
                                f"{hashlib.sha256(plan_id.encode()).hexdigest()[:24]}，"
                                "工程服务应该如何处理依赖异常？"
                            ),
                            "answer": (
                                "服务需要设置有限次数的指数退避重试；重试后仍失败时返回"
                                "可识别错误并触发降级，同时记录耗时、错误分类和请求标识，"
                                "以便监控告警、问题回放和版本回滚。"
                            ),
                            "supporting_excerpt": excerpt,
                        }
                        for plan_id in plan_ids
                    ],
                },
                ensure_ascii=False,
            )
        return "应设置超时重试、监控指标和回滚流程，并通过固定测试集验证效果。"

    async def close(self) -> None:
        self.closed = True


class DeterministicEmbeddingProvider:
    """按字符桶生成确定性向量，供 Vector/Hybrid 实验回归。"""

    async def embed(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.0] * 16
            for character in text.lower():
                vector[ord(character) % len(vector)] += 1.0
            vectors.append(vector)
        return vectors

    async def close(self) -> None:
        return None


class PassthroughReranker:
    """保持候选顺序的确定性 Reranker。"""

    async def rerank(
        self,
        query: str,
        results: list[SearchResult],
        *,
        top_k: int,
    ) -> list[SearchResult]:
        return results[:top_k]

    async def close(self) -> None:
        return None
