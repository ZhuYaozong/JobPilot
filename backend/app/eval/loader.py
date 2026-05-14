"""YAML → :class:`EvalCase` 解析器。

每个 YAML 文件可以包含一个或多个 case(顶层是 list[dict])。我们手写
解析而不是用 Pydantic,因为 case 结构会随未来 assertion 类型扩展,人工
dispatch + 明确报错比 Pydantic 错误链更利于作者迭代。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.eval.cases import AssertionSpec, EvalCase, FakeResponseRule, SeedSpec


def load_cases_from_yaml(path: Path) -> list[EvalCase]:
    """从单个 YAML 文件加载 case 列表。"""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if data is None:
        return []
    if not isinstance(data, list):
        raise ValueError(
            f"{path}: 顶层必须是 list[case dict],实际是 {type(data).__name__}",
        )
    return [_parse_case(entry, source=path) for entry in data]


def load_cases_from_dir(directory: Path) -> list[EvalCase]:
    """读 ``directory/*.yaml`` 并按文件名排序合并。

    顺序稳定,这样 baseline 文件名前缀(``01_``、``02_``)能控制报告顺序。
    """
    files = sorted(directory.glob("*.yaml")) + sorted(directory.glob("*.yml"))
    cases: list[EvalCase] = []
    for f in files:
        cases.extend(load_cases_from_yaml(f))
    return cases


def _parse_case(entry: dict[str, Any], *, source: Path) -> EvalCase:
    """转一份 dict 到 EvalCase。"""
    if not isinstance(entry, dict):
        raise ValueError(f"{source}: case 必须是 dict,实际 {type(entry).__name__}")
    name = entry.get("name")
    user_text = entry.get("user_text")
    if not name or not user_text:
        raise ValueError(f"{source}: case 缺少 name 或 user_text: {entry}")

    setup = [_parse_seed(item, source=source) for item in entry.get("setup") or []]
    fake = [
        _parse_fake_rule(item, source=source)
        for item in entry.get("fake_responses") or []
    ]
    assertions = [
        _parse_assertion(item, source=source) for item in entry.get("assertions") or []
    ]

    return EvalCase(
        name=str(name),
        user_text=str(user_text),
        description=str(entry.get("description") or ""),
        setup=setup,
        context=entry.get("context"),
        fake_responses=fake,
        assertions=assertions,
    )


def _parse_seed(item: dict[str, Any], *, source: Path) -> SeedSpec:
    if not isinstance(item, dict) or "kind" not in item:
        raise ValueError(f"{source}: setup 条目缺少 kind: {item}")
    return SeedSpec(
        kind=str(item["kind"]),
        params={k: v for k, v in item.items() if k not in {"kind", "ref"}},
        ref=item.get("ref"),
    )


def _parse_fake_rule(item: dict[str, Any], *, source: Path) -> FakeResponseRule:
    if "match" not in item or "response" not in item:
        raise ValueError(f"{source}: fake_responses 条目缺少 match 或 response: {item}")
    match = item["match"]
    if isinstance(match, str):
        match = [match]
    return FakeResponseRule(match=[str(m) for m in match], response=str(item["response"]))


def _parse_assertion(item: dict[str, Any], *, source: Path) -> AssertionSpec:
    if "type" not in item:
        raise ValueError(f"{source}: assertion 条目缺少 type: {item}")
    return AssertionSpec(
        type=str(item["type"]),
        params={k: v for k, v in item.items() if k not in {"type", "description"}},
        description=item.get("description"),
    )
