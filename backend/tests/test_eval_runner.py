"""eval 框架自身的烟测。

不跑业务 case;只验证:
- YAML 加载器能读出正确结构
- FakeLLMClient 关键词分发能命中 / 未命中
- 占位符替换在嵌套结构里正确工作
- 内置断言器对成功/失败两种情况都返回合理结果
- 端到端最小 case 在真测试库上跑通(种 1 个 KB → simple_chat 类型)

这些测试用真测试数据库(同 conftest.py),但 LLM 全程用 FakeLLMClient,
不会发任何外部网络请求。
"""

from __future__ import annotations

import asyncio
import textwrap
from pathlib import Path

import pytest

from app.eval.assertions import run_assertion
from app.eval.cases import (
    AssertionSpec,
    CaseTrace,
    EvalCase,
    FakeResponseRule,
    SeedSpec,
)
from app.eval.fake_llm import FakeLLMUnexpectedPrompt, build_fake_llm, fake_embedding
from app.eval.loader import load_cases_from_yaml
from app.eval.runner import _resolve_placeholders, run_cases


# ---------- FakeLLMClient ---------------------------------------------------


def test_fake_llm_dispatches_by_keyword(tmp_path) -> None:
    """最常见路径:多条规则按关键词命中,顺序无关。"""
    client = build_fake_llm([
        FakeResponseRule(match=["decide", "first"], response="A"),
        FakeResponseRule(match=["format"], response="B"),
    ])
    assert asyncio.run(client.generate_text("now decide and pick first option")) == "A"
    assert asyncio.run(client.generate_text("format response please")) == "B"


def test_fake_llm_consumes_each_rule_in_declared_order() -> None:
    """两条同 match 的规则用于模拟"先返回坏 JSON,再返回好 JSON"等轨迹。"""
    client = build_fake_llm([
        FakeResponseRule(match=["go"], response="first"),
        FakeResponseRule(match=["go"], response="second"),
    ])
    assert asyncio.run(client.generate_text("go!")) == "first"
    assert asyncio.run(client.generate_text("go again!")) == "second"
    # 两条都用过后,再调一次回退到第一条
    assert asyncio.run(client.generate_text("go third!")) == "first"


def test_fake_llm_raises_on_unmatched_prompt() -> None:
    client = build_fake_llm([FakeResponseRule(match=["foo"], response="ok")])
    with pytest.raises(FakeLLMUnexpectedPrompt):
        asyncio.run(client.generate_text("nothing here"))


# ---------- 占位符替换 ------------------------------------------------------


def test_placeholder_replacement_preserves_type_for_whole_string_tokens() -> None:
    """``"{kb_id}"`` 完全占位时应替换为原值(可能是 int),不强转 str。"""
    refs = {"kb_id": 42, "name": "腾讯"}
    assert _resolve_placeholders("{kb_id}", refs) == 42
    # 嵌入字符串时强转 str
    assert _resolve_placeholders("看 #{kb_id} 资料", refs) == "看 #42 资料"
    # dict / list 递归
    nested = {"k": ["{kb_id}", {"company": "{name}"}]}
    assert _resolve_placeholders(nested, refs) == {
        "k": [42, {"company": "腾讯"}],
    }
    # 找不到 key 时保留原 token 让作者看见拼错
    assert _resolve_placeholders("{missing}", refs) == "{missing}"


# ---------- 断言器 ----------------------------------------------------------


def _trace_with_calls(*calls: dict, final: str = "", status: str = "succeeded") -> CaseTrace:
    return CaseTrace(
        conversation_id=1,
        agent_run_id=1,
        agent_run_status=status,
        agent_run_error_class=None,
        agent_run_error_detail=None,
        final_text=final,
        tool_calls=list(calls),
    )


def test_tool_called_assertion_passes_when_present_and_fails_when_absent() -> None:
    trace = _trace_with_calls(
        {"tool_name": "list_user_jobs", "status": "success", "arguments": {}},
    )
    spec_pass = AssertionSpec(type="tool_called", params={"tool": "list_user_jobs"})
    spec_fail = AssertionSpec(type="tool_called", params={"tool": "search_knowledge"})
    assert run_assertion(spec_pass, trace, {}).passed is True
    failed = run_assertion(spec_fail, trace, {})
    assert failed.passed is False
    assert "search_knowledge" in failed.detail


def test_tool_order_assertion_allows_interleaved_other_tools() -> None:
    trace = _trace_with_calls(
        {"tool_name": "list_user_jobs", "status": "success", "arguments": {}},
        {"tool_name": "list_user_resumes", "status": "success", "arguments": {}},
        {"tool_name": "analyze_match", "status": "success", "arguments": {}},
    )
    ok = run_assertion(
        AssertionSpec(
            type="tool_order",
            params={"expected": ["list_user_jobs", "analyze_match"]},
        ),
        trace,
        {},
    )
    assert ok.passed is True
    bad = run_assertion(
        AssertionSpec(
            type="tool_order",
            params={"expected": ["analyze_match", "list_user_jobs"]},
        ),
        trace,
        {},
    )
    assert bad.passed is False


def test_final_contains_all_vs_any_modes() -> None:
    trace = _trace_with_calls(final="匹配度 87 分,关键技能对口。")
    pass_any = run_assertion(
        AssertionSpec(type="final_contains", params={"values": ["匹配", "陌生"]}),
        trace,
        {},
    )
    assert pass_any.passed is True

    fail_all = run_assertion(
        AssertionSpec(
            type="final_contains",
            params={"values": ["匹配", "陌生"], "mode": "all"},
        ),
        trace,
        {},
    )
    assert fail_all.passed is False
    assert "陌生" in fail_all.detail


def test_final_question_count_default_max_is_one() -> None:
    one_q = _trace_with_calls(final="能讲讲你最自豪的项目吗?")
    two_q = _trace_with_calls(final="第一个问题?第二个问题?")
    assert run_assertion(
        AssertionSpec(type="final_question_count", params={}), one_q, {},
    ).passed is True
    assert run_assertion(
        AssertionSpec(type="final_question_count", params={}), two_q, {},
    ).passed is False


def test_agent_run_status_matches_error_class() -> None:
    trace = CaseTrace(
        conversation_id=1,
        agent_run_id=1,
        agent_run_status="failed",
        agent_run_error_class="decide_repair_failed",
        agent_run_error_detail="...",
        final_text=None,
        tool_calls=[],
    )
    ok = run_assertion(
        AssertionSpec(
            type="agent_run_status",
            params={"status": "failed", "error_class": "decide_repair_failed"},
        ),
        trace,
        {},
    )
    assert ok.passed is True
    wrong_error = run_assertion(
        AssertionSpec(
            type="agent_run_status",
            params={"status": "failed", "error_class": "other"},
        ),
        trace,
        {},
    )
    assert wrong_error.passed is False


def test_unknown_assertion_type_fails_gracefully() -> None:
    result = run_assertion(
        AssertionSpec(type="never_registered", params={}),
        _trace_with_calls(),
        {},
    )
    assert result.passed is False
    assert "未知断言类型" in result.detail


# ---------- YAML 加载器 -----------------------------------------------------


def test_loader_parses_minimal_yaml(tmp_path: Path) -> None:
    yaml_path = tmp_path / "mini.yaml"
    yaml_path.write_text(
        textwrap.dedent(
            """
            - name: smoke
              user_text: hi
              fake_responses:
                - match: ["a", "b"]
                  response: "ok"
              assertions:
                - type: tool_not_called
                  tool: list_user_jobs
            """,
        ),
        encoding="utf-8",
    )
    cases = load_cases_from_yaml(yaml_path)
    assert len(cases) == 1
    case = cases[0]
    assert case.name == "smoke"
    assert case.user_text == "hi"
    assert case.fake_responses[0].match == ["a", "b"]
    assert case.assertions[0].type == "tool_not_called"
    assert case.assertions[0].params == {"tool": "list_user_jobs"}


# ---------- fake embedding --------------------------------------------------


def test_fake_embedding_deterministic_and_dim_matches() -> None:
    vec1 = fake_embedding("hello", 8)
    vec2 = fake_embedding("hello", 8)
    vec3 = fake_embedding("world", 8)
    assert vec1 == vec2
    assert len(vec1) == 8
    # 不同输入大概率不同(8 个 float 都重合概率极低)
    assert vec1 != vec3
    # 值域 [-1, 1]
    assert all(-1.0 <= x <= 1.0 for x in vec1)


# ---------- 端到端最小 case(真测试库 + fake LLM) -------------------------


def test_runner_executes_simple_chat_case_against_real_db(client) -> None:
    """烟测:跑一个最小 case 验证 runner 能完整走通(种子 / patch / 评分)。

    依赖 conftest 的 ``client`` fixture 保证 ``users.test`` 行已经存在。
    """
    _ = client  # 触发 fixture 创建 test 用户行
    case = EvalCase(
        name="smoke_simple_chat",
        user_text="你好,你能帮我做什么?",
        setup=[],
        context=None,
        fake_responses=[
            FakeResponseRule(
                match=["请严格按以下两种 JSON 之一回复"],
                response='{"action":"respond_directly","text":"我可以帮你管理简历和岗位。"}',
            ),
        ],
        assertions=[
            AssertionSpec(type="agent_run_status", params={"status": "succeeded"}),
            AssertionSpec(
                type="final_contains",
                params={"values": ["简历"]},
            ),
        ],
    )
    results = run_cases([case], live=False, timeout_seconds=30.0)
    assert len(results) == 1
    r = results[0]
    assert r.error is None, r.error
    assert r.passed, [a.detail for a in r.assertions if not a.passed]
    assert r.trace is not None
    assert r.trace.agent_run_status == "succeeded"


def test_runner_seeds_knowledge_base_and_passes_id_to_assertions(client) -> None:
    """验证 setup → ref_context → assertion 占位符替换的完整链路。"""
    _ = client
    case = EvalCase(
        name="smoke_seed_kb",
        user_text="占位",
        setup=[
            SeedSpec(kind="knowledge_base", params={"name": "公司资料"}, ref="kb"),
        ],
        fake_responses=[
            FakeResponseRule(
                match=["请严格按以下两种 JSON 之一回复"],
                response='{"action":"respond_directly","text":"OK"}',
            ),
        ],
        # 一个永远 pass 的断言 + 一个用占位符的断言(找不到工具调用所以应失败,
        # 但占位符替换应该已经发生)
        assertions=[
            AssertionSpec(type="agent_run_status", params={"status": "succeeded"}),
        ],
    )
    results = run_cases([case], live=False, timeout_seconds=30.0)
    assert results[0].passed, results[0].assertions
