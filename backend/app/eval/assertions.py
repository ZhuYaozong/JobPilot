"""内置断言器集合。

每个断言器是一个函数,签名:

    check(trace: CaseTrace, params: dict, ref_context: dict) -> AssertionResult

- ``trace`` 来自 runner,已经把 agent_run / tool_calls / final_text 摊平
- ``params`` 是 YAML case 里 assertion 块 ``params:`` 下的内容
- ``ref_context`` 是 seed 阶段产生的 id 别名表(``{"kb_id": 17, "job_id": 42}``)
  断言里可以写 ``"{kb_id}"`` 等占位符,runner 解析后传进来已经替换好

新增断言器只需 ``register("foo")`` 装饰一下即可,框架自动 dispatch。

``llm_judge`` 是特殊的异步断言器——需要调真实 LLM API。runner 通过
``run_assertion_async`` 入口来驱动;fake 模式下 ``llm_judge`` 被跳过,
标记为 skipped 而非 fail。
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from app.eval.cases import AssertionResult, AssertionSpec, CaseTrace


# {assertion_type: checker_fn}
_REGISTRY: dict[str, Callable[[CaseTrace, dict[str, Any], dict[str, Any]], AssertionResult]] = {}


def register(name: str) -> Callable[
    [Callable[[CaseTrace, dict[str, Any], dict[str, Any]], AssertionResult]],
    Callable[[CaseTrace, dict[str, Any], dict[str, Any]], AssertionResult],
]:
    """装饰器:把一个 checker 函数注册到 ``_REGISTRY``。"""

    def _wrap(fn):
        if name in _REGISTRY:
            raise ValueError(f"assertion 类型重名: {name}")
        _REGISTRY[name] = fn
        return fn

    return _wrap


def run_assertion(
    spec: AssertionSpec,
    trace: CaseTrace,
    ref_context: dict[str, Any],
) -> AssertionResult:
    """根据 spec.type 找 checker 并执行。

    未知 type 直接 fail —— eval 框架的契约错误不该当成"实际通过"。
    """
    checker = _REGISTRY.get(spec.type)
    if checker is None:
        return AssertionResult(
            spec=spec,
            passed=False,
            detail=f"未知断言类型: {spec.type}。已注册: {sorted(_REGISTRY)}",
        )
    try:
        return checker(trace, spec.params or {}, ref_context)
    except Exception as exc:  # noqa: BLE001 — 框架自身崩溃也算 fail,不上抛
        return AssertionResult(
            spec=spec,
            passed=False,
            detail=f"断言器内部异常: {type(exc).__name__}: {exc}",
        )


# ---------- 工具调用相关 ---------------------------------------------------


@register("tool_called")
def _tool_called(
    trace: CaseTrace, params: dict[str, Any], _refs: dict[str, Any],
) -> AssertionResult:
    """断言指定工具至少被调用过一次。可选 ``status`` 过滤(success/failed)。"""
    tool = params.get("tool")
    expected_status = params.get("status")  # None 表示不关心
    matched = [
        tc for tc in trace.tool_calls
        if tc.get("tool_name") == tool
        and (expected_status is None or tc.get("status") == expected_status)
    ]
    if not matched:
        called = [tc.get("tool_name") for tc in trace.tool_calls]
        return AssertionResult(
            spec=_make_spec("tool_called", params),
            passed=False,
            detail=f"工具 {tool!r} 未被调用(实际调用: {called})",
        )
    return AssertionResult(spec=_make_spec("tool_called", params), passed=True)


@register("tool_not_called")
def _tool_not_called(
    trace: CaseTrace, params: dict[str, Any], _refs: dict[str, Any],
) -> AssertionResult:
    """断言指定工具从未被调用。"""
    tool = params.get("tool")
    matched = [tc for tc in trace.tool_calls if tc.get("tool_name") == tool]
    if matched:
        return AssertionResult(
            spec=_make_spec("tool_not_called", params),
            passed=False,
            detail=f"工具 {tool!r} 被调用了 {len(matched)} 次,期望 0 次",
        )
    return AssertionResult(spec=_make_spec("tool_not_called", params), passed=True)


@register("tool_order")
def _tool_order(
    trace: CaseTrace, params: dict[str, Any], _refs: dict[str, Any],
) -> AssertionResult:
    """断言指定工具按顺序出现(允许中间穿插其他工具)。

    例如 expected=[A, B, C] 表示 A 在 B 之前、B 在 C 之前都被调用过。中间
    出现的其他工具不影响通过。
    """
    expected: list[str] = list(params.get("expected") or [])
    actual = [tc.get("tool_name") for tc in trace.tool_calls]
    i = 0
    for name in actual:
        if i < len(expected) and name == expected[i]:
            i += 1
    if i < len(expected):
        return AssertionResult(
            spec=_make_spec("tool_order", params),
            passed=False,
            detail=(
                f"工具顺序未满足。期望按序出现 {expected},实际调用 {actual},"
                f"卡在第 {i + 1} 个 ({expected[i]})"
            ),
        )
    return AssertionResult(spec=_make_spec("tool_order", params), passed=True)


@register("tool_args_contain")
def _tool_args_contain(
    trace: CaseTrace, params: dict[str, Any], _refs: dict[str, Any],
) -> AssertionResult:
    """断言某工具的至少一次调用,参数 dict 包含指定键值。

    用来验证 "agent 把对话上下文里的 kb_id 透传到了 search_knowledge 的
    knowledge_base_id 参数" 这类轨迹。
    """
    tool = params.get("tool")
    expected: dict[str, Any] = params.get("expected") or {}
    matched_calls = [tc for tc in trace.tool_calls if tc.get("tool_name") == tool]
    if not matched_calls:
        return AssertionResult(
            spec=_make_spec("tool_args_contain", params),
            passed=False,
            detail=f"工具 {tool!r} 未被调用,无法验证参数",
        )
    for call in matched_calls:
        args = call.get("arguments") or {}
        if all(args.get(k) == v for k, v in expected.items()):
            return AssertionResult(
                spec=_make_spec("tool_args_contain", params), passed=True,
            )
    return AssertionResult(
        spec=_make_spec("tool_args_contain", params),
        passed=False,
        detail=(
            f"工具 {tool!r} 的所有调用都没满足 {expected}。"
            f"实际参数: {[c.get('arguments') for c in matched_calls]}"
        ),
    )


# ---------- 最终回复相关 ---------------------------------------------------


@register("final_contains")
def _final_contains(
    trace: CaseTrace, params: dict[str, Any], _refs: dict[str, Any],
) -> AssertionResult:
    """断言最终回复包含指定关键词。

    ``values`` 是关键词列表(YAML 里可写成数字 / 字符串,这里统一转 str),
    ``mode`` = "any"(默认,任一命中即可)或 "all"(全部命中)。
    case-insensitive 由 ``case_sensitive=false`` 开启的反向行为暂不实现,
    中文场景大小写无意义。
    """
    raw_values = params.get("values") or []
    # YAML 里 ``- 87`` 会解析成 int,直接 ``v in final`` 会 TypeError。
    # 全部转 str,允许作者用数字字面表达"回复要含数字 87"。
    values: list[str] = [str(v) for v in raw_values]
    mode: str = params.get("mode") or "any"
    final = trace.final_text or ""
    if mode == "all":
        missing = [v for v in values if v not in final]
        ok = not missing
        detail = "" if ok else f"缺少关键词: {missing}; 实际回复: {final[:200]!r}"
    else:
        ok = any(v in final for v in values)
        detail = "" if ok else f"未命中任一关键词 {values}; 实际回复: {final[:200]!r}"
    return AssertionResult(spec=_make_spec("final_contains", params), passed=ok, detail=detail)


@register("final_matches_regex")
def _final_matches_regex(
    trace: CaseTrace, params: dict[str, Any], _refs: dict[str, Any],
) -> AssertionResult:
    """正则匹配最终回复。``pattern`` 必填,``flags`` 可选(默认 re.DOTALL)。"""
    pattern: str = params.get("pattern") or ""
    flags = re.DOTALL if params.get("dotall", True) else 0
    final = trace.final_text or ""
    if re.search(pattern, final, flags):
        return AssertionResult(spec=_make_spec("final_matches_regex", params), passed=True)
    return AssertionResult(
        spec=_make_spec("final_matches_regex", params),
        passed=False,
        detail=f"正则 {pattern!r} 未匹配;实际回复: {final[:200]!r}",
    )


# ---------- agent_run 状态相关 ---------------------------------------------


@register("agent_run_status")
def _agent_run_status(
    trace: CaseTrace, params: dict[str, Any], _refs: dict[str, Any],
) -> AssertionResult:
    """断言 agent_run.status 等于期望值(succeeded / failed 等)。

    可选 ``error_class`` 一并匹配。
    """
    expected_status: str = params.get("status") or ""
    expected_error: str | None = params.get("error_class")
    ok = trace.agent_run_status == expected_status and (
        expected_error is None or trace.agent_run_error_class == expected_error
    )
    if ok:
        return AssertionResult(spec=_make_spec("agent_run_status", params), passed=True)
    return AssertionResult(
        spec=_make_spec("agent_run_status", params),
        passed=False,
        detail=(
            f"期望 status={expected_status!r}"
            + (f" error_class={expected_error!r}" if expected_error else "")
            + f",实际 status={trace.agent_run_status!r}"
            + f" error_class={trace.agent_run_error_class!r}"
            + (f" error_detail={trace.agent_run_error_detail!r}" if trace.agent_run_error_detail else "")
        ),
    )


@register("final_question_count")
def _final_question_count(
    trace: CaseTrace, params: dict[str, Any], _refs: dict[str, Any],
) -> AssertionResult:
    """统计最终回复中"问号"出现次数。

    模拟面试模式的合规性检查:每轮只问一个问题 → 中文问号"?" / 英文 "?"
    总数应 <= ``max``(默认 1)。
    """
    max_q: int = int(params.get("max", 1))
    final = trace.final_text or ""
    # 显式按码点列举,避免源码里"?"被某些编辑器规范化掉,导致中英文问号
    # 都被算成同一个字符。
    ascii_q = "?"
    cjk_q = "？"
    count = final.count(ascii_q) + final.count(cjk_q)
    if count <= max_q:
        return AssertionResult(spec=_make_spec("final_question_count", params), passed=True)
    return AssertionResult(
        spec=_make_spec("final_question_count", params),
        passed=False,
        detail=f"问号出现 {count} 次,期望 ≤ {max_q};回复: {final[:200]!r}",
    )


# ---------- LLM-as-judge(异步断言) ----------------------------------------

# 标记哪些断言类型是异步的,runner 需要特殊处理
ASYNC_ASSERTION_TYPES: set[str] = set()


def register_async(name: str):
    """装饰器:注册一个异步 checker(签名返回 awaitable)。"""

    def _wrap(fn):
        if name in _REGISTRY:
            raise ValueError(f"assertion 类型重名: {name}")
        _REGISTRY[name] = fn
        ASYNC_ASSERTION_TYPES.add(name)
        return fn

    return _wrap


@register_async("llm_judge")
async def _llm_judge(
    trace: CaseTrace, params: dict[str, Any], _refs: dict[str, Any],
) -> AssertionResult:
    """用 LLM 对 agent 回复做软质量评分。

    必填参数:
    - ``rubric``: 评分标准描述(传给 judge LLM)

    可选参数:
    - ``threshold``: 归一化总分阈值,低于此值判 fail(默认 0.6)
    - ``context_desc``: 额外上下文说明(传给 judge LLM)
    """
    from app.eval.judge import run_judge

    rubric = params.get("rubric")
    if not rubric:
        return AssertionResult(
            spec=_make_spec("llm_judge", params),
            passed=False,
            detail="llm_judge 缺少必填参数 rubric",
        )

    threshold: float = float(params.get("threshold", 0.6))
    context_desc: str | None = params.get("context_desc")
    user_text: str = params.get("_user_text") or ""

    verdict = await run_judge(
        rubric=rubric,
        user_text=user_text,
        final_text=trace.final_text or "",
        tool_calls=trace.tool_calls,
        context_desc=context_desc,
    )

    passed = verdict.score >= threshold
    detail = "" if passed else (
        f"judge 评分 {verdict.score:.2f} 低于阈值 {threshold}; {verdict.reasoning[:200]}"
    )
    return AssertionResult(
        spec=_make_spec("llm_judge", params),
        passed=passed,
        detail=detail,
        score=verdict.score,
        judge_detail={
            "score": verdict.score,
            "threshold": threshold,
            "aspects": verdict.aspects,
            "reasoning": verdict.reasoning,
        },
    )


async def run_assertion_async(
    spec: AssertionSpec,
    trace: CaseTrace,
    ref_context: dict[str, Any],
) -> AssertionResult:
    """异步版断言执行入口,支持 ``llm_judge`` 等异步断言器。

    普通(同步)断言直接调用;异步断言 await。runner 统一走本函数。
    """
    checker = _REGISTRY.get(spec.type)
    if checker is None:
        return AssertionResult(
            spec=spec,
            passed=False,
            detail=f"未知断言类型: {spec.type}。已注册: {sorted(_REGISTRY)}",
        )
    try:
        if spec.type in ASYNC_ASSERTION_TYPES:
            return await checker(trace, spec.params or {}, ref_context)
        return checker(trace, spec.params or {}, ref_context)
    except Exception as exc:  # noqa: BLE001
        return AssertionResult(
            spec=spec,
            passed=False,
            detail=f"断言器内部异常: {type(exc).__name__}: {exc}",
        )


# ---------- 内部辅助 -------------------------------------------------------


def _make_spec(type_: str, params: dict[str, Any]) -> AssertionSpec:
    """断言失败信息回填时构造 spec,确保 ``AssertionResult.spec`` 总有值。"""
    return AssertionSpec(type=type_, params=dict(params or {}))
