"""Eval case 调度器。

入口 :func:`run_cases` 接收 ``EvalCase`` 列表 + 选项,执行:
1. 解析 case(把 yaml ``setup``、``context``、``assertions`` 转成 dataclass)
2. 给每个 case 分配独立 ``marker``,种子数据互不串台
3. 用 fake LLM(或真 LLM)跑 ``run_assistant_turn``
4. 从 DB 抽取 trace —— agent_run 状态 + tool 调用 + 工具参数/结果 +
   最终 assistant 文本
5. 按 case.assertions 逐条评分

每个 case 用独立 NullPool engine,行为对齐 backend/tests/conftest.py 的
``_run_with_fresh_engine`` —— 避免共享引擎 + asyncpg 在多事件循环下踩坑。
"""

from __future__ import annotations

import asyncio
import contextlib
import re
import time
from collections.abc import Iterable
from typing import Any
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.eval.assertions import run_assertion
from app.eval.cases import (
    AssertionResult,
    AssertionSpec,
    CaseResult,
    CaseTrace,
    EvalCase,
    SeedSpec,
)
from app.eval.fake_llm import FakeLLMClient, build_fake_llm, fake_embedding
from app.eval.fixtures import SEEDERS, new_marker, resolve_test_user
from app.llm.client import LLMClient
from app.llm.embedding_client import EmbeddingClient
from app.models.agent_run import AgentRun
from app.models.message import Message
from app.models.tool_call_log import ToolCallLog
from app.schemas.assistant import AssistantRunRequest, ContextSelection
from app.services.assistant_service import run_assistant_turn


# 单 case 兜底超时(秒)。fake LLM 模式下每 case 1-2 秒,真 LLM 上限较大。
# 主要防止 case 配置错误把 workflow 卡死。
DEFAULT_CASE_TIMEOUT_SECONDS = 120.0


def run_cases(
    cases: Iterable[EvalCase],
    *,
    live: bool = False,
    timeout_seconds: float = DEFAULT_CASE_TIMEOUT_SECONDS,
) -> list[CaseResult]:
    """同步入口,内部 ``asyncio.run`` 每个 case。

    ``live=True`` 表示用真 ``LLMClient`` 而不是 fake;此时 case 的
    ``fake_responses`` 被忽略,需要 ``LLM_*`` 环境变量已配置。
    """
    results: list[CaseResult] = []
    for case in cases:
        result = asyncio.run(
            _run_single_case(case, live=live, timeout_seconds=timeout_seconds),
        )
        results.append(result)
    return results


async def _run_single_case(
    case: EvalCase, *, live: bool, timeout_seconds: float,
) -> CaseResult:
    """跑一个 case,生成 :class:`CaseResult`。

    异常一律捕获并作为框架错误塞进 ``CaseResult.error``;真正的 case fail
    走 assertions 路径。这样 runner 永远跑完所有 case,不被一个挂掉拦腰
    打断。
    """
    started = time.perf_counter()
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    try:
        trace: CaseTrace | None = None
        ref_context: dict[str, Any] = {}
        framework_error: str | None = None
        # EmbeddingClient patch 跨整个 case 生命周期;LLMClient patch 在
        # _execute_case 里 seed 完之后 enter,因为 fake_responses 的 response
        # 文本可能引用刚种好的 id(``"{resume_id}"`` 占位符)。
        with _embedding_patch(live=live):
            async with AsyncSession(engine, expire_on_commit=False) as db:
                try:
                    trace, ref_context = await asyncio.wait_for(
                        _execute_case(db, case, live=live),
                        timeout=timeout_seconds,
                    )
                except asyncio.TimeoutError:
                    framework_error = f"case 超时(> {timeout_seconds}s)"
                except Exception as exc:  # noqa: BLE001 — 框架错误统一兜底
                    framework_error = f"{type(exc).__name__}: {exc}"

        if framework_error is not None or trace is None:
            return CaseResult(
                case=case,
                passed=False,
                duration_ms=int((time.perf_counter() - started) * 1000),
                assertions=[],
                error=framework_error or "trace 未生成",
            )

        # assertion 评分独立于工作流执行,不需要 DB 会话。
        # 评分前先把 params 里的 ``{ref}`` 占位符替换成实际 id —— 这样
        # case 作者可以用 ``resume_id: "{resume_id}"`` 来引用种子产物。
        assertion_results: list[AssertionResult] = [
            run_assertion(
                AssertionSpec(
                    type=spec.type,
                    params=_resolve_placeholders(spec.params, ref_context),
                    description=spec.description,
                ),
                trace,
                ref_context,
            )
            for spec in case.assertions
        ]
        passed = all(r.passed for r in assertion_results) if assertion_results else True
        return CaseResult(
            case=case,
            passed=passed,
            duration_ms=int((time.perf_counter() - started) * 1000),
            assertions=assertion_results,
            trace=trace,
        )
    finally:
        await engine.dispose()


async def _execute_case(
    db: AsyncSession,
    case: EvalCase,
    *,
    live: bool,
) -> tuple[CaseTrace, dict[str, Any]]:
    """执行 case 的主流程,返回 (trace, ref_context)。"""
    user = await resolve_test_user(db)
    marker = new_marker()

    # ref_context 收集 seed 阶段产生的 id 别名,后续在 context / fake_responses
    # / assertion 占位符替换里使用。
    ref_context: dict[str, Any] = {"marker": marker, "user_id": user.id}
    for spec in case.setup:
        await _seed_one(db, user, marker, spec, ref_context)

    # 占位符要替换的对象:context(传给 workflow)和 fake_responses 的
    # response 文本(LLM 输出的 JSON 里要带真实 id)。
    payload_context = _resolve_context(case.context, ref_context)
    fake_rules = _resolve_fake_responses(case.fake_responses, ref_context)

    fake_client: FakeLLMClient | None = (
        None if live else build_fake_llm(fake_rules)
    )

    payload = AssistantRunRequest(
        conversation_id=None,
        content=case.user_text,
        context=ContextSelection(**payload_context) if payload_context else None,
    )

    # workflow 注入的 llm_client 给 decide / format_response / summarize 用;
    # action 工具内部新建的 LLMClient 通过 :func:`_llm_patch` 也代理到同一
    # 个 fake_client,所以两条路径行为一致。
    llm_client: LLMClient | FakeLLMClient = (
        LLMClient() if (live or fake_client is None) else fake_client
    )

    with _llm_patch(fake_client=fake_client, live=live):
        response = await run_assistant_turn(
            db,
            user,
            payload,
            llm_client=llm_client,  # type: ignore[arg-type]  # fake 实现等价接口
        )

    trace = await _collect_trace(db, response.conversation_id, response.agent_run.id)
    return trace, ref_context


def _resolve_fake_responses(
    rules: list[Any], refs: dict[str, Any],
) -> list[Any]:
    """把 fake response 文本里的 ``{ref}`` 替换成实际 id。

    由于 ``FakeResponseRule.response`` 经常是 LLM 输出的 JSON 字面值
    (``{"args": {"resume_id": "{resume_id}"}}``),替换后 JSON 解析能拿到
    真正的 int / str。``match`` 关键词列表也走同一个替换,允许 case 作者
    在关键词里引用占位符(虽然不常用)。
    """
    from app.eval.cases import FakeResponseRule

    return [
        FakeResponseRule(
            match=[_resolve_placeholders(m, refs) for m in rule.match],
            response=_resolve_placeholders(rule.response, refs),
        )
        for rule in rules
    ]


async def _seed_one(
    db: AsyncSession,
    user,
    marker: str,
    spec: SeedSpec,
    ref_context: dict[str, Any],
) -> None:
    """跑一条 setup 条目。"""
    seeder = SEEDERS.get(spec.kind)
    if seeder is None:
        raise ValueError(
            f"未知 seed kind: {spec.kind!r}。已注册: {sorted(SEEDERS)}",
        )
    resolved_params = _resolve_placeholders(spec.params, ref_context)
    new_id = await seeder(db, user, marker=marker, **resolved_params)
    if spec.ref:
        ref_context[f"{spec.ref}_id"] = new_id


async def _collect_trace(
    db: AsyncSession, conversation_id: int, agent_run_id: int,
) -> CaseTrace:
    """从 DB 抽取断言需要的全部事实。

    用列元组 select 而不是 ORM 实例,避免 detached/expired 风险(同
    assistant_service 末尾的做法)。
    """
    db.expire_all()

    run_row = (
        await db.execute(
            select(
                AgentRun.id,
                AgentRun.status,
                AgentRun.error_class,
                AgentRun.error_detail,
            ).where(AgentRun.id == agent_run_id),
        )
    ).one()

    final_text_row = (
        await db.execute(
            select(Message.content)
            .where(
                Message.agent_run_id == agent_run_id,
                Message.role == "assistant",
            )
            .order_by(Message.sequence_no.desc())
            .limit(1),
        )
    ).first()
    final_text = final_text_row[0] if final_text_row else None

    tool_rows = (
        await db.execute(
            select(
                ToolCallLog.tool_name,
                ToolCallLog.status,
                ToolCallLog.arguments_json,
                ToolCallLog.result_json,
                ToolCallLog.error_class,
                ToolCallLog.error_detail,
                ToolCallLog.latency_ms,
            )
            .where(ToolCallLog.agent_run_id == agent_run_id)
            .order_by(ToolCallLog.id),
        )
    ).all()
    tool_calls = [
        {
            "tool_name": row.tool_name,
            "status": row.status,
            "arguments": dict(row.arguments_json or {}),
            "result": dict(row.result_json or {}) if row.result_json else None,
            "error_class": row.error_class,
            "error_detail": row.error_detail,
            "latency_ms": row.latency_ms,
        }
        for row in tool_rows
    ]

    return CaseTrace(
        conversation_id=conversation_id,
        agent_run_id=run_row.id,
        agent_run_status=run_row.status,
        agent_run_error_class=run_row.error_class,
        agent_run_error_detail=run_row.error_detail,
        final_text=final_text,
        tool_calls=tool_calls,
    )


# ---------- 占位符解析 -----------------------------------------------------


_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def _resolve_placeholders(value: Any, refs: dict[str, Any]) -> Any:
    """把任意嵌套结构里的 ``"{key}"`` 占位符替换为 ``refs[key]``。

    设计:
    - 整字符串就是占位符(``"{kb_id}"``)→ 直接换成 refs[key] 原值(保留 int)
    - 字符串里嵌占位符(``"hello {marker} world"``)→ str(refs[key]) 拼接
    - 找不到 key → 保留原文,让作者通过日志意识到拼错了
    """
    if isinstance(value, str):
        match = _PLACEHOLDER_RE.fullmatch(value)
        if match and match.group(1) in refs:
            return refs[match.group(1)]

        def _sub(m: re.Match[str]) -> str:
            return str(refs.get(m.group(1), m.group(0)))

        return _PLACEHOLDER_RE.sub(_sub, value)
    if isinstance(value, list):
        return [_resolve_placeholders(item, refs) for item in value]
    if isinstance(value, dict):
        return {k: _resolve_placeholders(v, refs) for k, v in value.items()}
    return value


def _resolve_context(
    context: dict[str, Any] | None, refs: dict[str, Any],
) -> dict[str, Any] | None:
    """case.context 块的占位符解析。

    返回 None 时表示 case 没声明 context,运行时把 ContextSelection 留空。
    """
    if not context:
        return None
    return _resolve_placeholders(context, refs)


# ---------- EmbeddingClient patch -----------------------------------------


@contextlib.contextmanager
def _embedding_patch(*, live: bool):
    """非 live 模式下把 ``EmbeddingClient.embed`` 替换为 deterministic 假实现。

    search_knowledge / 未来的 RAG 工具会调用真嵌入服务,跑 eval 时既不想
    花钱也不想引入网络抖动。这个 contextmanager 在 case 执行期间替换方法,
    退出时自动恢复 —— 用 ``unittest.mock.patch`` 而不是手动赋值,这样
    异常退出也能正确清理。
    """
    if live:
        # 真 LLM 跑也要用真 embedding 才有意义,直接放行
        yield
        return

    async def _fake_embed(self: EmbeddingClient, texts: list[str]) -> list[list[float]]:
        dim = self.dimensions
        return [fake_embedding(t, dim) for t in texts]

    with patch.object(EmbeddingClient, "embed", _fake_embed):
        yield


@contextlib.contextmanager
def _llm_patch(*, fake_client: FakeLLMClient | None, live: bool):
    """非 live 模式下把 ``LLMClient.generate_text`` 代理到 ``fake_client``。

    Action 工具(match_analysis / cover_letter / interview_prep / tailored_
    resume)内部会直接 ``LLMClient()`` 新建客户端,绕过 workflow 注入。
    我们在这一层 patch 整个类的方法,保证所有调用路径都路由到同一个
    fake_client,case 作者的 ``fake_responses`` 是单一事实源。
    """
    if live or fake_client is None:
        yield
        return

    async def _patched(self: LLMClient, prompt: str) -> str:
        return await fake_client.generate_text(prompt)

    with patch.object(LLMClient, "generate_text", _patched):
        yield
