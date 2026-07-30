# JobPilot 500 条 Agent 配对评测

本实验把独立 LoRA evaluation 数据中的 500 条领域问答送入完整 JobPilot
LangGraph Agent，对比 `jobpilot-base` 和 `jobpilot-lora-v1`。

这批数据没有简历、岗位或知识库上下文，因此正确路线通常是
`respond_directly`。它主要评估 Agent 决策 JSON、错误工具调用、停止行为以及
LangGraph 包装后的回答质量；专门的工具路由能力仍由
`backend/app/eval/datasets_live/agent_no_rag_v1.yaml` 评估。

## 控制变量

- Base/LoRA 使用相同的 500 个 `plan_id`。
- 数据集 SHA256 固定为配置中的值，与训练集精确 Prompt 重叠为 0。
- 请求级排除 `search_knowledge`，不需要停止 RAG 服务。
- 每个 case 创建独立 `is_test_user`，避免数据库历史数据串台。
- 每完成一条就追加 JSONL；重复运行会跳过已有结果。

## 2026-07-30 全量结果

| 指标 | Base | LoRA |
| --- | ---: | ---: |
| 工作流成功率 | 78.8% | 99.6% |
| 完整 case 通过率 | 78.6% | 88.4% |
| 无工具直答率 | 78.6% | 88.4% |
| 错误工具调用率 | 0.2% | 11.2% |
| 重复工具调用率 | 0.2% | 7.6% |
| RAG 工具调用次数 | 0 | 0 |
| P95 延迟 | 16.941 秒 | 7.792 秒 |

Base 的 106 条失败均归为 `decide_repair_failed`，代表性原因是回答文本中的换行没有
按 JSON 字符串规则转义。LoRA 只有 2 条同类失败，但在泛化的简历/JD 问题上容易误调
`analyze_match`、`generate_tailored_resume` 等需要用户资源的工具。RAG 调用为 0，
证明请求级 `search_knowledge` 隔离生效；下一轮实验应分别增强决策 JSON 鲁棒性和
“咨询问题 vs. 操作用户资源”的工具边界，然后使用同一 500 个 `plan_id` 重跑。

## 12 条预检

在项目根目录执行：

```powershell
uv --cache-dir .uv-cache --directory backend run python -m app.eval.agent_pair_cli --config ../evaluation/agent/config.json --run-name smoke-12 --sample-per-task 2

uv --cache-dir .uv-cache --directory backend run python -m app.eval.agent_pair_report --config ../evaluation/agent/config.json --run-name smoke-12
```

## 500 条全量

```powershell
uv --cache-dir .uv-cache --directory backend run python -m app.eval.agent_pair_cli --config ../evaluation/agent/config.json --run-name full

uv --cache-dir .uv-cache --directory backend run python -m app.eval.agent_pair_report --config ../evaluation/agent/config.json --run-name full
```

只重跑失败记录：

```powershell
uv --cache-dir .uv-cache --directory backend run python -m app.eval.agent_pair_cli --config ../evaluation/agent/config.json --run-name full --retry-failed
```

报告同时输出 Agent 成功率、无工具直答率、错误/重复工具调用、RAG 泄漏、
延迟、文本相似度、数字风险、单轮直调差异和 30 条盲评材料。
