"""Eval case 数据模型。

一个 ``EvalCase`` 描述一个完整的对话场景:
- ``setup`` 列出测试数据库里要预先种的资源(知识库、文档、岗位、简历、
  投递等),每条可以带 ``ref`` 别名,后续 ``context`` 和 ``assertions``
  可以用 ``"{kb_id}"``、``"{job_id}"`` 之类的占位符引用
- ``user_text`` 是模拟用户在 chat 里发的消息
- ``context`` 模拟前端 ContextPanel 的选择(知识库 / 简历 / 岗位 / 模式)
- ``fake_responses`` 配置 FakeLLMClient 在不同 prompt 阶段返回什么(关键词
  → 响应文本)。为空时 case 需要 ``--live`` 才能跑
- ``assertions`` 是确定性断言列表,每条对应 :mod:`app.eval.assertions`
  里的一个 checker

所有字段都用 ``dataclass`` 而不是 Pydantic,因为 case 来源是 YAML 文件,
我们自己 dispatch 校验,逻辑比 Pydantic 警告链更可读。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SeedSpec:
    """种子数据条目。

    ``kind`` 决定铺什么(``knowledge_base`` / ``knowledge_document`` /
    ``resume`` / ``job`` / ``application``),``params`` 是该 kind 的字段值。
    ``ref`` 是别名:种好之后会把生成的资源 id 写到 ``ctx[ref + "_id"]``,
    后续条目和断言可以用 ``"{kb_id}"`` 这样的占位符引用。
    """

    kind: str
    params: dict[str, Any]
    ref: str | None = None


@dataclass
class FakeResponseRule:
    """FakeLLMClient 的一条匹配规则。

    ``match`` 是若干关键词的列表,只要 prompt 同时包含全部关键词就视为命中
    (顺序无所谓)。匹配后返回 ``response`` 字面值。规则按声明顺序遍历,
    第一个命中的胜出 —— 因此越具体的规则要放越前面。
    """

    match: list[str]
    response: str


@dataclass
class AssertionSpec:
    """一条断言。

    ``type`` 必须是 :mod:`app.eval.assertions` 里注册过的 checker 名;
    ``params`` 是该 checker 的具体参数(关键词 / 工具名 / 严格度等)。
    通过 ``description`` 提供可读名,失败时报告里会显示。
    """

    type: str
    params: dict[str, Any]
    description: str | None = None


@dataclass
class EvalCase:
    """完整 case。

    至少要有 ``name`` 和 ``user_text``。其余字段都是可选默认空。
    """

    name: str
    user_text: str
    description: str = ""
    setup: list[SeedSpec] = field(default_factory=list)
    context: dict[str, Any] | None = None
    fake_responses: list[FakeResponseRule] = field(default_factory=list)
    assertions: list[AssertionSpec] = field(default_factory=list)


@dataclass
class AssertionResult:
    """单条断言的评分结果。

    ``detail`` 在 fail 时填可读原因(给 markdown 报告看),pass 时通常为空。
    """

    spec: AssertionSpec
    passed: bool
    detail: str = ""


@dataclass
class CaseTrace:
    """工作流执行后的可观察事实,供 assertion 评分使用。

    刻意只放 *已落库 / 已序列化* 的字段;不放 ORM 对象,避免断言函数被会
    话状态干扰。
    """

    conversation_id: int
    agent_run_id: int
    agent_run_status: str
    agent_run_error_class: str | None
    agent_run_error_detail: str | None
    final_text: str | None
    tool_calls: list[dict[str, Any]]  # 每项含 tool_name / status / arguments / result


@dataclass
class CaseResult:
    """一个 case 的最终评分 + 全部诊断信息。

    Runner 输出的核心数据结构,Reporter 读它生成 markdown 和 JSON。
    """

    case: EvalCase
    passed: bool
    duration_ms: int
    assertions: list[AssertionResult]
    trace: CaseTrace | None = None
    # 框架自身崩溃时填,例如 seed 失败、yaml 字段错。区别于"工作流跑完
    # 但断言 fail"——后者 ``error`` 留空,失败信息在 ``assertions`` 里。
    error: str | None = None
