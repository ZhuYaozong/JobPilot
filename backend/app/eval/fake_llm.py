"""可注入的"假" LLM 客户端,用于 eval 离线复现。

设计原则:
- 接口对齐 ``app.llm.client.LLMClient.generate_text(prompt) -> str``,这样
  ``run_assistant_turn(..., llm_client=fake)`` 直接可用,workflow 完全感知
  不到差异
- 不重写 prompt 解析:case 作者声明一组"关键词 → 响应文本"规则,客户端
  按声明顺序匹配并返回。规则越具体放越前面
- 显式拒绝匹配不到任何规则的 prompt:抛 ``FakeLLMUnexpectedPrompt`` 让 case
  作者注意到自己漏配了响应分支。沉默 fallback 会让评测变成"无意义通过"

不预设"prompt 是 decide 还是 format_response":由 case 作者用关键词去区分
(例如 decide 的 prompt 含 "请严格按以下两种 JSON 之一回复",
format_response 含 "本轮你为了回答用户的问题")。

本模块同时暴露 :func:`fake_embedding` 给 search_knowledge 这类需要查询向量
的工具使用 —— eval runner 在非 live 模式下把 ``EmbeddingClient.embed``
patch 成它,这样工具能跑完整逻辑而不真发 HTTP。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.eval.cases import FakeResponseRule


class FakeLLMUnexpectedPrompt(RuntimeError):
    """case 没给当前 prompt 配响应。

    抛出时附带 prompt 的前 400 字,方便作者定位哪条 LLM 调用缺规则。
    """

    def __init__(self, prompt: str) -> None:
        preview = prompt[:400]
        super().__init__(
            "FakeLLMClient 收到未配置响应的 prompt:\n" + preview,
        )
        self.prompt_preview = preview


@dataclass
class FakeLLMClient:
    """实现 ``LLMClient`` 等价接口的伪客户端。

    用 ``dataclass`` 而非继承真实 ``LLMClient``,避免它的 ``__init__`` /
    设置耦合进来。``run_assistant_turn`` 只接触 ``generate_text``,这就够了。
    """

    rules: list[FakeResponseRule]
    # 已匹配的次数,用于一份规则要在同一 turn 里被多次命中时,允许 case
    # 作者在 yaml 里写多条同 match 的规则模拟"先这样后那样"的轨迹。
    _call_count: int = 0

    async def generate_text(self, prompt: str) -> str:
        # 收集所有命中的规则(关键词全部出现),按声明顺序返回。同一个 prompt
        # 命中多条时,优先用还没用过的;全用过了再退化到第一条。
        candidates: list[tuple[int, FakeResponseRule]] = [
            (idx, rule)
            for idx, rule in enumerate(self.rules)
            if all(token and token in prompt for token in rule.match)
        ]
        if not candidates:
            raise FakeLLMUnexpectedPrompt(prompt)

        # 优先选用次数最少的命中规则,实现"多条同 match 按顺序消费"的效果。
        # ``_consumed`` 用规则 id 标识(它是 dataclass 默认 unhashable,这里
        # 用列表索引即可)。
        if not hasattr(self, "_consumed"):
            self._consumed: list[int] = []
        unused = [c for c in candidates if c[0] not in self._consumed]
        idx, rule = (unused[0] if unused else candidates[0])
        self._consumed.append(idx)
        self._call_count += 1
        return rule.response


def build_fake_llm(rules: list[FakeResponseRule]) -> FakeLLMClient:
    """构造 FakeLLMClient 实例。

    单独包一层是为了将来如果要叠加"录制 + 回放"等模式,case 作者侧的写法
    可以保持不变。
    """
    return FakeLLMClient(rules=list(rules))


def fake_embedding(text: str, dim: int) -> list[float]:
    """文本 → [-1, 1] 范围的稳定向量,长度 = ``dim``。

    用 SHA-256 把文本字节展平,再 mod 到 [-1, 1]。性质:
    - 同样输入永远同样输出(deterministic)
    - 不同文本几乎不会撞向量(有 256-bit hash 兜底)
    - 不会出现全 0,避免 pgvector ``<=>`` 在两端零向量上产生 NaN

    eval runner 在非 live 模式下把 ``EmbeddingClient.embed`` patch 成对每个
    文本调用本函数;``test_knowledge_indexing.py`` 也用同款做法,保持
    "测试 / eval / production" 三套都自洽。
    """
    seed = hashlib.sha256(text.encode("utf-8")).digest()
    raw = (seed * (dim // len(seed) + 1))[:dim]
    return [(b / 127.5) - 1.0 for b in raw]
