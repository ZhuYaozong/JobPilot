# JobPilot 数据生产与实验评测工程

该目录服务于 JobPilot 的大模型应用实验闭环：

- LoRA/SFT：生产简历优化、JD 匹配、面试问答、项目深挖、Agent/RAG 技术和系统设计数据。
- RAG：生成或导入领域文档，并生产带原文证据的独立评测集。
- 模型实验：统一比较 Vector、BM25、Hybrid 与 Hybrid + Rerank；回答模型仍可独立切换 Base / LoRA。
- Agent：训练数据和知识库为 Agent 提供能力基础；工具选择、状态流转和业务副作用继续由 `backend/app/eval` 做行为回归。

本工程不会在安装或导入模块时自动调用模型；正式数据只会由显式生成命令写入输出目录。

## 仓库内正式数据快照

当前仓库包含 2026-07-23 使用 `deepseek-v4-flash` 通过 OpenAI-compatible
接口生成的正式数据。最终质量检查结果为 0 错误、0 警告、精确重复 0、近似重复 0：

| 数据 | 数量 | 平均有效长度 |
| --- | ---: | ---: |
| SFT train | 3000 | output 186.60 字 |
| SFT val | 300 | output 182.81 字 |
| SFT test | 300 | output 185.67 字 |
| LoRA 独立评测 | 500 | output 183.41 字 |
| RAG 文档 | 50 | 1427.36 字 |
| RAG 评测 | 200 | answer 62.83 字 |

正式数据保留在 `lora/`、`rag/documents/` 和 `evaluation/`。`.work/` 中的模型原始响应、
checkpoint、用量日志以及 `reports/` 中的本地报告不会提交到 Git。

## 输出目录

```text
datasets/
├── lora/
│   ├── train.jsonl             # 3000 条
│   ├── val.jsonl               # 300 条
│   ├── test.jsonl              # 300 条
│   └── manifest.jsonl          # split、任务类型和记录哈希
├── rag/
│   ├── documents/              # 默认生成约 50 篇，也可导入外部文档
│   ├── generated_manifest.jsonl
│   └── external_manifest.jsonl
├── evaluation/
│   ├── rag_test.jsonl          # 200 条独立 RAG 评测
│   ├── lora_test.jsonl         # 500 条独立 LoRA 效果评测
│   └── lora_manifest.jsonl     # LoRA 评测类别和记录哈希
└── reports/
    ├── quality_report.json
    ├── quality_report.md
    └── experiments/
        ├── experiment_cases.jsonl
        ├── experiment_report.json
        └── experiment_report.md
```

SFT 正式文件严格只包含：

```json
{"instruction": "", "input": "", "output": ""}
```

RAG 评测文件包含：

```json
{
  "question": "",
  "answer": "",
  "source_document": "rag/documents/example.md",
  "supporting_excerpt": ""
}
```

`supporting_excerpt` 必须是源文档中连续存在的原文，用于检查数据可溯源性以及计算检索证据召回。

## 环境安装

```powershell
cd D:\code\JobPilot
$env:UV_CACHE_DIR='D:\code\JobPilot\.uv-cache'
uv sync --project datasets --extra dev
```

程序读取当前进程环境变量，不会主动解析或打印 `.env` 文件中的密钥。`.env.example` 只作为变量清单；可以通过 PowerShell、CI Secret 或现有环境管理工具注入变量。

常规 OpenAI-compatible 调用所需变量：

```powershell
$env:DATASET_LLM_BASE_URL='https://api.openai.com/v1'
$env:DATASET_LLM_API_KEY='...'
$env:DATASET_GENERATOR_MODEL='...'
```

`base_url` 应填写 API 根路径，Provider 会自动追加 `/chat/completions`。兼容 OpenAI、vLLM、SGLang 及其他实现 Chat Completions 协议的服务。

大批量正式生产可用 `DATASET_RUNTIME_CONCURRENCY` 临时覆盖生成并发数。它不参与数据配置指纹，不影响 checkpoint 恢复；实际取值仍应服从模型服务的并发与限流策略。

## 先检查计划

```powershell
uv run --project datasets jobpilot-datasets plan --config datasets\config.yaml
uv run --project datasets python datasets\scripts\generate.py --config datasets\config.yaml --dry-run
```

默认计划：

| 数据 | 数量 |
| --- | ---: |
| SFT train | 3000 |
| SFT val | 300 |
| SFT test | 300 |
| 独立 LoRA 评测 | 500 |
| 生成 RAG 文档 | 50 |
| RAG 评测 | 200 |

SFT 的每个 split 都在六类任务之间严格等分。LoRA 评测独立生成，并与三个 SFT split 做跨集合去重。文档尽量均匀覆盖 LLM 基础、Transformer、RAG、Agent、LangGraph、MCP、LoRA/SFT、AI 工程实践八个领域。

## 生成数据

推荐按完整流水线运行：

```powershell
uv run --project datasets python datasets\scripts\generate.py `
  --config datasets\config.yaml `
  --stage all
```

也可以按阶段执行：

```powershell
# LoRA SFT
uv run --project datasets python datasets\scripts\generate.py `
  --config datasets\config.yaml `
  --stage sft

# RAG 文档
uv run --project datasets python datasets\scripts\generate.py `
  --config datasets\config.yaml `
  --stage rag-documents `
  --resume

# 基于文档生成 RAG 评测
uv run --project datasets python datasets\scripts\generate.py `
  --config datasets\config.yaml `
  --stage rag-evaluation `
  --resume

# 独立 LoRA 效果评测
uv run --project datasets python datasets\scripts\generate.py `
  --config datasets\config.yaml `
  --stage lora-evaluation `
  --resume
```

中断后使用同一个配置和 `--resume` 继续：

```powershell
uv run --project datasets python datasets\scripts\generate.py `
  --config datasets\config.yaml `
  --stage all `
  --resume
```

小规模连通性测试可以使用 `--limit`，但不能和 `--stage all` 一起使用：

```powershell
uv run --project datasets python datasets\scripts\generate.py `
  --config datasets\config.yaml `
  --stage sft `
  --limit 12
```

部分生成只写入 `.work/` checkpoint，不会覆盖正式 JSONL。某一阶段全部通过质量门禁后，程序才会原子写入最终文件。

### Checkpoint 行为

`.work/` 保存：

- 确定性生成计划；
- 已接受样本；
- 每次拒绝的规则原因和截断响应；
- 配置指纹和阶段完成状态。

配置发生变化时，旧 checkpoint 会被拒绝，避免不同实验配置混入同一数据集。此时应保留旧目录用于审计，并在配置中切换新的 `paths.work_dir`。

## 使用本地 Qwen

安装可选依赖：

```powershell
uv sync --project datasets --extra qwen
```

把 `config.yaml` 中的：

```yaml
generation:
  provider: generator
```

改为：

```yaml
generation:
  provider: qwen_local_example
```

并设置：

```powershell
$env:QWEN_MODEL_PATH='D:\models\Qwen-Instruct'
```

本地 Provider 使用 `transformers` 的 chat template 和 `model.generate`。GPU 推理默认并发为 1；需要连续批处理或高并发时，建议使用 vLLM/SGLang 启动 OpenAI-compatible 服务，再切回 API Provider。

## 导入外部文档

支持 `.md`、`.txt`，安装 `documents` extra 后还支持 `.pdf`、`.docx`：

```powershell
uv sync --project datasets --extra documents

uv run --project datasets python datasets\scripts\import_documents.py `
  D:\knowledge `
  --recursive `
  --config datasets\config.yaml
```

导入过程：

1. 读取并抽取文本；
2. 检查有效长度；
3. 按正文 SHA-256 去重；
4. 转换为带来源 front matter 的 Markdown；
5. 写入 `rag/external_manifest.jsonl`。

`DocumentSource` 是扩展接口。后续接入网页抓取、对象存储、数据库或 JobPilot 用户知识库时，只需实现 `discover()` 与 `extract()`，无需修改生成和评测逻辑。

## 数据质量检查

```powershell
uv run --project datasets python datasets\scripts\check_quality.py `
  --config datasets\config.yaml
```

框架刚安装、尚未生成正式数据时，可以验证 Schema 和目录配置：

```powershell
uv run --project datasets python datasets\scripts\check_quality.py `
  --config datasets\config.yaml `
  --allow-missing
```

质量门禁包括：

- JSON Schema 和 Pydantic 双层校验；
- 数量与六类任务分布；
- SFT 问题/回答长度；
- 工程实践信号；
- 精确重复和中文近似重复；
- train/val/test 交叉泄漏；
- Markdown 标题、概念、原理和实践案例章节；
- 文档正文长度和 manifest 哈希；
- RAG `source_document` 是否存在；
- `supporting_excerpt` 是否确实来自源文档。

报告写入 `reports/quality_report.json` 和 `reports/quality_report.md`。严格检查未通过时脚本返回非零退出码，适合接入 CI。

## Hybrid RAG 对照实验

先配置回答模型、Embedding 和 Reranker 端点：

```powershell
$env:BASE_MODEL_BASE_URL='http://127.0.0.1:8001/v1'
$env:BASE_MODEL_NAME='base-model'
$env:EMBEDDING_BASE_URL='http://127.0.0.1:8003/v1'
$env:EMBEDDING_MODEL_NAME='BAAI/bge-m3'
$env:RERANKER_BASE_URL='http://127.0.0.1:8004/v1'
$env:RERANKER_MODEL_NAME='BAAI/bge-reranker-v2-m3'
```

`config.yaml` 已把实验 Embedding 固定校验为 1024 维，并设置 `send_dimensions: false`，适配 BGE-M3 常见的 OpenAI-compatible 部署。若服务实现了可变维度扩展，可显式改为 `send_dimensions: true`；返回维度无论如何都会被校验。Reranker 输出的是 query-passage 相关性分数，不使用 pgvector 维度。

运行：

```powershell
uv run --project datasets python datasets\scripts\run_experiments.py `
  --config datasets\config.yaml
```

连通性测试：

```powershell
uv run --project datasets python datasets\scripts\run_experiments.py `
  --config datasets\config.yaml `
  --limit 10
```

默认实验矩阵：

| Variant | 召回方式 | Rerank |
| --- | --- | --- |
| Vector RAG | 向量 | 否 |
| BM25 RAG | BM25 | 否 |
| Hybrid RAG | Vector + BM25 + RRF | 否 |
| Hybrid + Rerank | Vector + BM25 + RRF | 是 |

每个 `experiments.variants` 条目可独立设置 `retrieval_strategy: none | vector | bm25 | hybrid` 和 `reranker_enabled`。旧配置中的 `use_rag` 仍兼容：为 `true` 时使用 `experiments.retriever.kind`，为 `false` 时不注入上下文。回答模型仍由 variant 的 `provider` 独立选择，因此也可以继续组织 Base / LoRA 对照。

检索指标：

- Recall@K：前 K 个结果覆盖标注相关源文档的比例；
- MRR：正确源文档首次出现排名的倒数；
- Evidence Recall：`supporting_excerpt` 被检索片段覆盖的比例。

回答指标：

- Answer Score：Token F1 与 ROUGE-L 的均值；
- Faithfulness：候选回答内容被标注证据覆盖的比例；
- JSON 明细同时保留 Token F1、ROUGE-L 和 Source Support；
- 可选 LLM-as-judge：正确性、相关性、可溯源性、工程质量。

若启用 Judge，在 `experiments.judge_provider` 中填写 Provider 名称。确定性文本指标适合持续回归，Judge 适合补充语义判断，二者不应互相替代。

## 去重和可复现性

去重分三步：

1. Unicode NFKC、大小写、标点和空白规范化；
2. SHA-256 精确去重；
3. 中文字符 n-gram 候选召回，再使用 SimHash 与编辑相似度复核。

全局 seed 决定任务计划、场景组合、生成顺序、split 和每条请求 seed。云端模型是否能够逐字符复现取决于服务端实现，因此实验报告和 checkpoint 同时保存配置指纹和任务 ID。

## 安全与成本

- API Key 只来自环境变量，不写入配置指纹、数据集或报告。
- 模型原始响应只在拒绝记录中保留最多 1000 字符。
- 所有正式输出通过临时文件原子替换。
- 外部文档目标文件名经过路径字符过滤，评测读取限制在数据输出根目录。
- `plan` 和 `--dry-run` 可在调用模型前估算最少批次数。
- 正式生产前建议先用 `--limit` 验证模型 JSON 稳定性，再根据拒绝率调整 batch、并发和成本预算。
