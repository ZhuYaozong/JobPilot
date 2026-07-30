# Base / LoRA Agent + Hybrid RAG 配对评测

这组实验与 `evaluation/agent` 的无 RAG Agent 评测不同：每条问题都会经过真实
`AssistantService → LangGraph → search_knowledge → Hybrid + Rerank → 最终回答`
链路。Base 和 LoRA 使用同一份200条问题、同一个只读评测知识库，唯一实验变量是
生成模型。

## 实验约束

- 数据：`datasets/evaluation/rag_test.jsonl`，共200条。
- 语料：`datasets/rag/documents`，共50份Markdown。
- Agent只看得到 `search_knowledge`，避免其他业务工具干扰。
- `respond_directly` 仍是合法Agent动作；选择直答会被记为RAG路由失败。
- 检索固定为等权Hybrid，随后使用 `bge-reranker-v2-m3` 重排。
- 评测进程强制关闭Vector与Reranker的fail-open，避免静默降级。
- 每条问题创建独立会话，但共用一个只读测试用户和专用知识库。
- 输出目录 `results/` 被Git忽略，避免提交模型原始回答和数据库ID。

## 第一次准备知识库

在 `backend` 目录、已配置 `.env` 且Embedding/Reranker服务在线时执行：

```powershell
uv run python -m app.eval.agent_rag_pair_cli `
  --config ../evaluation/agent_rag/config.json `
  --prepare-kb `
  --prepare-only
```

如果冻结文档发生合法变更，需要显式重建专用评测库：

```powershell
uv run python -m app.eval.agent_rag_pair_cli `
  --config ../evaluation/agent_rag/config.json `
  --rebuild-kb `
  --prepare-only
```

`--rebuild-kb` 只删除固定测试用户 `_agent_rag_eval_v1` 下、描述带评测标记的
`agent-rag-eval-v1`，不会修改普通用户知识库。

## 冒烟与正式运行

先跑前10条、两个模型共20次Agent turn：

```powershell
uv run python -m app.eval.agent_rag_pair_cli `
  --config ../evaluation/agent_rag/config.json `
  --run-name smoke `
  --limit 10

uv run python -m app.eval.agent_rag_pair_report `
  --config ../evaluation/agent_rag/config.json `
  --run-name smoke
```

冒烟通过后运行完整400次Agent turn：

```powershell
uv run python -m app.eval.agent_rag_pair_cli `
  --config ../evaluation/agent_rag/config.json `
  --run-name full

uv run python -m app.eval.agent_rag_pair_report `
  --config ../evaluation/agent_rag/config.json `
  --run-name full
```

中断后重复相同命令会跳过已有 `case_id`；只重跑失败样本时增加
`--retry-failed`。

基础设施故障应按错误类型补跑，避免重试掩盖真实模型协议失败。例如只补
`llm_unavailable`：

```powershell
uv run python -m app.eval.agent_rag_pair_cli `
  --config ../evaluation/agent_rag/config.json `
  --run-name full `
  --retry-failed `
  --retry-error-class llm_unavailable
```

本次正式运行中SSH转发曾中断，造成Base后34条和LoRA首轮200条
`llm_unavailable`。恢复隧道后只补跑该错误类型；Base的
`decide_repair_failed` 没有重跑，因此不会通过选择性重试美化模型结果。

## 输出

- `preflight.json`：数据哈希、知识库完整性、服务探测和实际RAG配置。
- `run_metadata.json`：模型、样本和运行参数。
- `jobpilot-base.jsonl` / `jobpilot-lora-v1.jsonl`：逐条Agent轨迹。
- `summary.json`：机器可读汇总。
- `report.md`：Agent路由、检索、回答和成对结论。
- `paired_cases.csv`：逐题Base/LoRA对照表。
- `blind_review.jsonl`：40条匿名人工盲审材料。

自动指标需要结合盲审解释。尤其是不同模型会自主改写不同的检索query，因此两组
召回结果不同是Agent能力差异的一部分，并非控制变量失效。

## 2026-07-30 正式结果

专用知识库完整性检查为50份ready文档、148个chunk、1024维Embedding；正式结果中
没有残留基础设施失败。

| 指标 | Base Agent + RAG | LoRA Agent + RAG |
| --- | ---: | ---: |
| 工作流成功率 | 92.50% | 100.00% |
| 完整单次RAG路由通过率 | 62.00% | 36.50% |
| 选择检索工具率 | 74.00% | 43.00% |
| 无检索直答率 | 26.00% | 57.00% |
| 多次检索率 | 6.50% | 6.50% |
| 参数完全重复调用率 | 2.50% | 5.50% |
| 选择检索后的Source Hit | 99.32% | 96.51% |
| 选择检索后的MRR | 0.9327 | 0.8953 |
| 选择检索后的证据召回 | 0.9417 | 0.8942 |
| 两模型工作流都成功时Answer Score | 0.4215 | 0.2839 |
| 平均端到端延迟 | 5.161秒 | 4.379秒 |
| P95端到端延迟 | 10.116秒 | 9.475秒 |

185个两模型都成功的样本中，LoRA胜/平/Base胜为59/1/125；LoRA - Base Answer
Score为-0.1376，Bootstrap 95% CI为 `[-0.1734, -0.1032]`。只看两模型都完成
单次正确RAG路由的56条，Base/LoRA Answer Score为0.5156/0.4116，差值95% CI为
`[-0.1588, -0.0508]`，Base优势仍然存在。

这说明检索器不是主要瓶颈：Agent一旦选择检索，两组Source Hit都超过96%。Base的
主要缺陷是15条 `decide_repair_failed`，均来自回答文本中的换行或反斜杠没有按严格
JSON转义；LoRA工作流全部成功，但57%的样本选择直答，尤其MCP领域24条全部没有检索。
因此当前知识问答Agent优先使用Base + Hybrid + Rerank；LoRA继续用于求职领域生成，
后续应补充知识库路由和严格JSON协议的训练样本后再复测。
