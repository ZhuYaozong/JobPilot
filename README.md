# JobPilot

JobPilot 是面向求职者的 AI Copilot。它把岗位收集、简历管理、匹配分析、求职材料生成、模拟面试、知识库检索和投递跟进放进同一条工作流，帮助用户从看到一个岗位一路推进到定制材料、准备面试和持续跟进。

当前项目已经完成核心 MVP 闭环，并进入 Agent + RAG 产品化阶段：后端有真实的 FastAPI API、LangGraph 工作流、OpenAI-compatible LLM / Embedding client、BM25 + pgvector 混合检索层；前端有 Vue 3 + Element Plus 的求职工作台、SSE 流式 AI 助手、知识库管理和多类材料生成入口。

## Architecture

### Core Flow

下面展示从 Vue WebUI 发起请求，经 FastAPI、AssistantService、LangGraph 工作流与工具调用，到 SSE 响应和 PostgreSQL / pgvector 持久化的核心链路。

<p align="center">
  <img src="docs/images/readme/jobpilot-core-flow.png" alt="JobPilot Core Flow 核心流程图" width="100%" />
</p>

```text
JobPilot/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routers
│   │   ├── agent/        # LangGraph workflow, prompts, tools, tool adapter
│   │   ├── core/         # Settings
│   │   ├── db/           # Async SQLAlchemy session
│   │   ├── llm/          # OpenAI-compatible chat and embedding clients
│   │   ├── models/       # SQLAlchemy models
│   │   ├── schemas/      # Pydantic schemas
│   │   └── services/     # Business services and AI generation services
│   ├── alembic/
│   └── tests/
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── layouts/
│   │   ├── router/
│   │   ├── types/
│   │   └── views/
├── infra/
├── compose.yaml
└── README.md
```

后端分层原则：

- API 层只处理 HTTP、依赖注入和响应模型。
- Service 层承载业务校验、数据库写入和生成逻辑。
- Agent Tool 只做参数 schema、用户作用域和业务服务适配。
- LangGraph 只负责编排，不替代业务 service。
- LLM / Embedding 调用通过自研 OpenAI-compatible client，避免业务代码绑定具体供应商。

## Highlights

- 求职工作台：岗位、简历、匹配、材料、投递、AI 助手、知识库七个核心入口。
- 真实 AI 工作流：解析 JD / 简历，生成匹配分析、求职信、面试准备和定制简历。
- Agent Runtime：基于 LangGraph 1.x 的多节点工作流，支持工具调用、运行记录和 SSE 流式返回。
- MCP 双向集成：Assistant 可通过 Streamable HTTP 动态发现并调用白名单外部工具；同时提供独立、只读的 JobPilot MCP Server。
- RAG 知识库：支持资料上传、手工文本、切片、Vector / BM25 / Hybrid 检索、可选 Reranker 和 chunk 预览。
- AI 实验数据闭环：独立 `datasets` 工程生产 LoRA SFT、RAG 文档和带证据评测集，并比较 Vector、BM25、Hybrid、Hybrid + Rerank。
- 交互式模拟面试：基于当前岗位、简历、匹配结果、interview_prep 和 search_knowledge 逐轮提问。
- 定制简历版本：针对岗位生成 `ai_tailored` 简历版本，保留版本号、来源类型和变更摘要，前端可查看 / 复制 / 导出 Markdown 与 DOCX。
- 多用户认证：JWT 注册 / 登录 / me 与 dev 模式（`X-User-Name`）并存；侧边栏支持多会话切换、登录其他、注册新用户、退出登录。
- AI 草稿入口：岗位 / 简历创建抽屉里粘文本或贴 URL，LLM 自动推断公司 / 岗位 / 城市或标题并抽取结构化字段，编辑后一次落库；同样的 `draft_*` / `create_*` 工具也接入了 AI 助手，可以直接在对话里完成起草、确认、保存。
- 工程约束清晰：不引入 `langchain-openai`、`langchain-community`、`langchain-text-splitters`，模型调用由自研 OpenAI-compatible client 承载。

## Product Scope

JobPilot 当前覆盖的求职主链路：

```text
保存岗位或抓取岗位 URL
↓
上传或录入简历
↓
解析 JD 与简历
↓
生成岗位匹配分析
↓
生成求职信 / 面试准备 / 定制简历版本
↓
选择上下文与知识库进入 AI 助手
↓
基于工具与 RAG 继续追问、复盘、模拟面试
↓
记录投递阶段和下一步动作
```

## Feature Matrix

| 模块 | 当前能力 |
| --- | --- |
| 首页 | 展示最近岗位、简历、匹配、材料和投递进展，给出今日建议动作 |
| 岗位管理 | 创建、编辑、删除岗位；从 URL 抓取 JD 预览；AI 草稿（文本 / URL → LLM 自动填字段）；结构化解析 JD |
| 简历管理 | 创建、编辑、删除简历；上传 PDF / DOCX / TXT / MD；AI 草稿（粘文本 → LLM 推断标题 + 结构化）；版本卡片可查看 / 复制 / 导出 Markdown 与 DOCX |
| 匹配分析 | 选择岗位和简历生成匹配分、优势、短板、缺失关键词和修改建议 |
| 求职材料 | 生成求职信、面试准备；记录材料反馈；查看历史材料 |
| 定制简历 | 针对岗位生成 `ai_tailored` 简历版本，版本号按 `max(version_no)+1` 递增 |
| 投递跟进 | 创建投递记录、更新阶段、记录下一步动作和阶段事件时间线 |
| AI 助手 | Conversation / Message 持久化，LangGraph 工具调用，SSE 流式进度与回复 |
| 模拟面试 | 在 `mock_interview` 模式下结合岗位、简历、匹配结果、面试准备和知识库逐轮提问 |
| 知识库 | 知识库 CRUD、文档上传/粘贴、同步切片与 embedding、重新索引、chunk 预览 |
| RAG 检索 | Agent 工具 `search_knowledge` 按配置使用 BM25、pgvector 或 Hybrid，并可接 Reranker |

## 界面预览

下面截图来自 JobPilot 本地演示环境，覆盖求职工作台、AI 助手、知识库、匹配分析和投递跟进等核心页面。

### AI 助手：从匹配到模拟面试

AI 助手支持在同一会话里选择简历、岗位、投递记录和知识库作为上下文，通过 LangGraph 工具调用完成匹配分析、材料生成、模拟面试和深度追问。

<table>
  <tr>
    <td width="50%">
      <strong>匹配简历与岗位</strong><br />
      <sub>AI 助手可以读取当前简历和岗位，调用匹配分析工具并给出优势、短板和后续材料建议。</sub>
      <img src="docs/images/readme/assistant-match.png" alt="AI 助手匹配简历和岗位" />
    </td>
    <td width="50%">
      <strong>进入模拟面试</strong><br />
      <sub>在模拟面试模式下，助手会结合岗位、简历、匹配结果和知识库逐轮追问。</sub>
      <img src="docs/images/readme/assistant-interview.png" alt="AI 助手模拟面试" />
    </td>
  </tr>
  <tr>
    <td colspan="2">
      <strong>围绕项目与架构继续深挖</strong><br />
      <sub>用户可以继续追问 Agent、RAG、工具依赖、后端校验等实现细节，适合面试复盘和表达打磨。</sub>
      <img src="docs/images/readme/assistant-deep-dive.png" alt="AI 助手深度追问" />
    </td>
  </tr>
</table>

### 求职工作台：状态、资料与进度

首页聚合最近岗位、简历、匹配分析和投递状态；知识库沉淀公司资料、项目素材、面试笔记；投递跟进用看板记录每个岗位所处阶段。

<table>
  <tr>
    <td width="50%">
      <strong>首页总览</strong><br />
      <sub>集中查看目标岗位、已准备简历、匹配分析和最近活动。</sub>
      <img src="docs/images/readme/dashboard.png" alt="JobPilot 首页总览" />
    </td>
    <td width="50%">
      <strong>知识库管理</strong><br />
      <sub>上传资料后自动切片并写入向量库，AI 助手可限定在所选知识库内检索。</sub>
      <img src="docs/images/readme/knowledge.png" alt="JobPilot 知识库管理" />
    </td>
  </tr>
  <tr>
    <td width="50%">
      <strong>投递跟进看板</strong><br />
      <sub>按已收藏、已投递、筛选中、笔试/测评、面试中、Offer、已结束等阶段管理投递。</sub>
      <img src="docs/images/readme/applications.png" alt="JobPilot 投递跟进看板" />
    </td>
    <td width="50%">
      <strong>岗位与简历匹配分析</strong><br />
      <sub>展示匹配分、优势、短板、缺失关键词和简历修改建议，并可继续生成求职材料。</sub>
      <img src="docs/images/readme/matches.png" alt="JobPilot 岗位与简历匹配分析" />
    </td>
  </tr>
</table>

## Screens And Routes

| 路由 | 页面 |
| --- | --- |
| `/login` | 登录 / 注册(JWT) |
| `/` | 首页 |
| `/jobs` | 岗位管理 |
| `/resumes` | 简历管理 |
| `/matches` | 岗位与简历匹配度 |
| `/applications` | 投递跟进 |
| `/assistant` | AI 助手与模拟面试 |
| `/knowledge` | 知识库管理 |
| `/artifacts` | 求职材料历史页 |

## Tech Stack

### Backend

- FastAPI
- SQLAlchemy async
- Alembic
- PostgreSQL + pgvector
- Redis
- LangGraph 1.x
- LangChain-core 1.x
- httpx
- uv

### Frontend

- Vue 3
- Vite
- TypeScript
- Vue Router
- Axios
- Element Plus

### AI And Retrieval

- OpenAI-compatible Chat Completions API
- OpenAI-compatible Embeddings API
- 自研文本切片器
- pgvector semantic search
- SSE streaming assistant response
- MCP Python SDK 1.x（Streamable HTTP Client / Server）
- LoRA / RAG 数据生产、JSON Schema 校验、近似去重和离线模型组合实验

## Dataset And Experiment Lab

仓库根目录的 `datasets/` 是独立 Python 3.12 数据工程，服务于 JobPilot 的
LoRA 微调、RAG 增强和 Agent 实验闭环。它支持 OpenAI-compatible API、本地
Qwen、外部 Markdown/TXT/PDF/DOCX 导入、checkpoint 恢复和质量报告。

默认生产目标为：

- LoRA SFT：train 3000、val 300、test 300；
- LoRA evaluation：500 条与 SFT 三个 split 跨集合去重的独立问题；
- RAG：八个领域约 50 篇 Markdown 文档；
- RAG evaluation：200 条包含源文档和原文证据的问题；
- RAG 实验矩阵：Vector、BM25、Hybrid、Hybrid + Rerank；各 variant 可独立选择 Base 或 LoRA 回答模型。

仓库当前包含一份通过正式流水线生成的数据快照：

| 数据集 | 数量 | 质量状态 |
| --- | ---: | --- |
| LoRA SFT train / val / test | 3000 / 300 / 300 | Schema、Pydantic、去重通过 |
| LoRA 独立评测 | 500 | 与 SFT 跨集合泄漏检查通过 |
| RAG Markdown 文档 | 50 | 章节、长度、重复检查通过 |
| RAG 独立评测 | 200 | 证据原文一致性检查通过 |

正式数据不包含生成服务的 API Key。模型响应、checkpoint、运行日志和本地质量报告由
`.gitignore` 排除；如需重新生成，可使用同一配置和 `--resume` 安全续跑。

```powershell
uv sync --project datasets --extra dev
uv run --project datasets jobpilot-datasets plan --config datasets\config.yaml
uv run --project datasets python datasets\scripts\check_quality.py `
  --config datasets\config.yaml
```

完整配置、生成、外部文档导入和实验说明见
[`datasets/README.md`](datasets/README.md)。

## Model Topology And Verified Status

2026-07-30 完成了模型产物、运行服务和 500 条配对评测审计。服务是否在线是
瞬时状态，下面的“已验证”表示产物和调用链真实跑通，不表示服务必须常驻：

| 模型 | 职责 | 部署位置与接口 | 已验证状态 |
| --- | --- | --- | --- |
| Qwen2.5-7B-Instruct | Base 生成模型 | RTX 3090，vLLM `jobpilot-base` | 4 个分片、14.19 GiB，16384 上下文，真实 Chat API 通过 |
| JobPilot LoRA r16 | 求职领域生成模型 | 同一 vLLM 动态 adapter `jobpilot-lora-v1` | 154.05 MiB，rank 16，真实 Chat API 通过 |
| BAAI/bge-m3 | 召回 embedding | RTX 4060，`POST /v1/embeddings` | FP16、1024 维，pgvector 全量重建与 Vector 召回通过 |
| BAAI/bge-reranker-v2-m3 | Cross-encoder 精排 | RTX 4060，`POST /v1/rerank` | FP16，双模型共存和排序冒烟通过；不写入 pgvector |

Base 和 LoRA 共用一份 Base 权重，通过请求中的 `model` 字段切换；Embedding 与
Reranker 使用独立 `j-rag` 环境，避免影响 LLaMA-Factory 的 `j-train` 和 vLLM 的
`j-serve`。完整部署说明见 [`deploy/vllm/README.md`](deploy/vllm/README.md) 和
[`services/rag_models/README.md`](services/rag_models/README.md)。

### 当前评测结论

| 指标（500 条独立配对） | Base | LoRA |
| --- | ---: | ---: |
| 单轮字符 F1 | 0.2102 | 0.4464 |
| 单轮平均延迟 | 11.756 秒 | 2.231 秒 |
| Agent 工作流成功率 | 78.8% | 99.6% |
| Agent 完整 case 通过率 | 78.6% | 88.4% |
| Agent 错误工具调用率 | 0.2% | 11.2% |
| Agent 重复工具调用率 | 0.2% | 7.6% |
| RAG 工具泄漏次数 | 0 | 0 |

LoRA 明显提升领域回答相似度、输出收敛速度和 Agent 决策 JSON 成功率，但还不能只凭
自动指标宣布“全面优于 Base”：LoRA 的新增数字声明率更高，并且容易把通用简历/JD
问题误判为操作用户资源；Base 的主要失败是回答中的未转义换行导致严格 JSON 决策解析
失败。人工盲评尚未完成，后续应分别优化 Agent 协议鲁棒性和工具意图边界，再用同一
500 条数据重跑。详细报告生成方式和解读边界见
[`evaluation/llm/README.md`](evaluation/llm/README.md) 与
[`evaluation/agent/README.md`](evaluation/agent/README.md)。

### RAG 检索层评测

2026-07-30 使用 `datasets/rag/documents` 的 50 篇文档和
`datasets/evaluation/rag_test.jsonl` 的 200 条黄金问题完成了纯检索对照；全程不调用
生成模型：

| 策略 | Recall@5 | MRR | 证据召回 | 平均延迟 | P95 延迟 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Vector | 0.9850 | 0.9231 | 0.9278 | 556.7 ms | 593 ms |
| BM25 | 0.9950 | 0.9514 | 0.9729 | 3.1 ms | 5 ms |
| Hybrid | 0.9950 | 0.9506 | 0.9743 | 539.4 ms | 597 ms |
| Hybrid + Rerank | 0.9950 | 0.9642 | 0.9809 | 1074.6 ms | 1171 ms |

Hybrid + Rerank 是当前质量优先候选，BM25 是延迟优先基线；等权 Hybrid 没有比 BM25
获得稳定收益，因此不会仅凭本次离线实验自动修改生产 `RAG_STRATEGY`。四种策略共同漏召回
的唯一问题缺少主题限定，属于评测集歧义，当前保留原始样本并在报告中披露。完整复现命令
和指标边界见 [`datasets/README.md`](datasets/README.md#hybrid-rag-对照实验)。

进一步使用每篇文档 1 条问题组成 50 条调参集、剩余 150 条作为隔离验证集，扫描了
14 组 Hybrid 权重、RRF 和候选倍数。调参集第一名没有在验证集上胜过原始配置；最终仍由
`vector_weight=1`、`bm25_weight=1`、`rrf_k=60`、`candidate_multiplier=3`
获得最高验证综合分。生产参数因此保持不变，避免把调参集上的偶然提升当成泛化收益。

## MCP Integration

JobPilot 采用“内部业务工具保持本地调用，外部能力通过 MCP 接入”的双向架构：

- **MCP Client**：Assistant 每轮工作流前发现管理员配置的外部工具，并将它们以
  `mcp__<server_id>__<tool_name>` 命名空间加入统一 ToolCatalog。适合接入岗位搜索、
  公司调研等能力。
- **JobPilot MCP Server**：独立 ASGI 服务，只读暴露岗位、简历、投递、材料和知识库。
  它使用短期、audience 绑定、`jobpilot:read` scope 的专用 JWT，不接受普通网页 API token。
- 外部 MCP 结果被视为不可信数据，统一执行白名单、参数 JSON Schema 校验、结果限长、
  超时、错误映射和敏感信息隔离。
- 外部岗位搜索结果不会自动落库；仍然必须经过 `draft_job → 用户确认 → create_job`。

远程 Server 配置示例：

```env
MCP_ENABLED=true
JOB_SEARCH_MCP_TOKEN=replace-with-remote-token
MCP_SERVERS_JSON=[{"id":"jobs","url":"https://jobs.example.com/mcp","category":"job_search","allowed_tools":["search_jobs","get_job_detail"],"auth_token_env":"JOB_SEARCH_MCP_TOKEN"}]
```

启动只读 JobPilot MCP Server：

```powershell
uv --cache-dir .uv-cache --directory backend run uvicorn app.mcp_server.app:app --host 127.0.0.1 --port 8001
```

已登录用户先通过 `POST /api/auth/mcp-token` 获取一小时有效的 MCP 专用 bearer token，
再把 `http://127.0.0.1:8001/mcp` 和该 token 配置到支持 Streamable HTTP 的 MCP Client。
公网部署必须把 API 与 MCP URL 都改为 HTTPS，并关闭 `AUTH_DEV_MODE`。

## Quick Start

### 1. Clone And Install

```powershell
git clone https://github.com/ZhuYaozong/JobPilot.git
cd JobPilot
```

### 2. Start Infrastructure

```powershell
docker compose up -d
```

默认服务：

| Service | URL |
| --- | --- |
| PostgreSQL + pgvector | `127.0.0.1:25432` |
| Redis | `127.0.0.1:26379` |

### 3. Configure Environment

```powershell
Copy-Item .env.example .env
Copy-Item backend/.env.example backend/.env
Copy-Item frontend/.env.example frontend/.env
```

后端最小配置：

```env
DATABASE_URL=postgresql+asyncpg://postgres:123456@127.0.0.1:25432/jobpilot
REDIS_URL=redis://127.0.0.1:26379/0

LLM_BASE_URL=https://api.example.com/v1
LLM_API_KEY=your-api-key
LLM_MODEL_NAME=your-chat-model

EMBEDDING_BASE_URL=http://127.0.0.1:7997/v1
EMBEDDING_API_KEY=local-no-auth
EMBEDDING_MODEL_NAME=BAAI/bge-m3
EMBEDDING_DIMENSIONS=1024
EMBEDDING_SEND_DIMENSIONS=false

# 默认 vector；也可切换为 bm25 / hybrid
RAG_STRATEGY=vector
RAG_RERANKER_ENABLED=false

AUTH_SECRET_KEY=change-this-to-a-long-random-secret
AUTH_DEV_MODE=true
```

Embedding 配置可以独立指定；如果未设置 endpoint，客户端会在运行时尝试复用对应的 `LLM_*` 配置。当前 schema 与 BGE-M3 dense embedding 统一为 1024 维。`EMBEDDING_SEND_DIMENSIONS=false` 适配固定输出维度、但不接受 OpenAI `dimensions` 参数的自建服务；客户端仍会严格校验返回值必须为 1024 维。

RAG 检索已支持 `vector`、`bm25` 和基于加权 RRF 的 `hybrid`。可选 Reranker 使用独立 `/rerank` 端点；完整参数和四种切换示例见 `backend/README.md`。默认仍为 Vector RAG 且关闭重排，便于兼容和快速回滚。

从旧 1536 维索引升级时，先阅读 [backend/README.md](backend/README.md) 的“BGE-M3 维度迁移”章节。迁移会保留文档和 chunk 文本、清空不可复用的旧向量，再由批量脚本安全重建；在向量尚未补齐时可临时使用 `RAG_STRATEGY=bm25`。

本地 RTX GPU 上同时运行 BGE-M3 与 bge-reranker-v2-m3 的安装、版本锁定和 API 测试见 [本地 RAG 模型服务](services/rag_models/README.md)；正式切换数据库前按 [BGE-M3 迁移运行手册](docs/rag/bge-m3-migration-runbook.md) 完成备份与只读预演。

合并本次代码不会自动修改现有数据库或调用模型服务。BGE-M3 服务、数据库备份和维护窗口准备完成前，可以继续运行旧版本配置；正式切换时再按迁移章节执行 Alembic 和向量重建脚本。

`POSTGRES_PASSWORD=123456` 和 `AUTH_DEV_MODE=true` 只面向本地开发。对外部署前请至少设置 `APP_ENV=production`、`APP_DEBUG=false`、`AUTH_DEV_MODE=false`，并替换 `AUTH_SECRET_KEY`、数据库密码和所有模型 API key。

### 4. Install Backend Dependencies

```powershell
uv --cache-dir .uv-cache --directory backend sync
```

### 5. Run Migrations

```powershell
uv --cache-dir .uv-cache --directory backend run alembic upgrade head
```

### 6. Start Backend

```powershell
uv --cache-dir .uv-cache --directory backend run uvicorn app.main:app --reload
```

Backend:

```text
http://localhost:8000
GET /health
GET /health/db
```

### 7. Start Frontend

```powershell
cd frontend
npm install
npm run dev
```

Frontend:

```text
http://localhost:5173
```

## API Overview

业务 API 主要挂载在 `/api/v1` 下；auth router 走 `/api/auth`(不带 `/v1`):

| Domain | Endpoints |
| --- | --- |
| Auth | `/api/auth/register`, `/api/auth/login`, `/api/auth/me` |
| MCP Auth | `/api/auth/mcp-token` |
| Resumes | `/api/v1/resumes`, `/api/v1/resumes/upload`, `/api/v1/resumes/draft-from-input`, `/api/v1/resumes/{id}/parse` |
| Resume Versions | `/api/v1/resume-versions`, `/api/v1/resume-versions/generate-tailored`, `/api/v1/resume-versions/{id}/export` |
| Jobs | `/api/v1/jobs`, `/api/v1/jobs/fetch-from-url`, `/api/v1/jobs/draft-from-input`, `/api/v1/jobs/{id}/parse` |
| Matches | `/api/v1/matches`, `/api/v1/matches/analyze` |
| Applications | `/api/v1/applications`, `/api/v1/applications/{id}/transition`, `/api/v1/applications/{id}/events` |
| Artifacts | `/api/v1/artifacts`, `/api/v1/artifacts/generate-cover-letter`, `/api/v1/artifacts/generate-interview-prep`, `/api/v1/artifacts/{id}/export` |
| Conversations | `/api/v1/conversations`, `/api/v1/conversations/{id}/messages`, `/api/v1/conversations/{id}/agent-runs` |
| Assistant | `/api/v1/assistant/run`, `/api/v1/assistant/run-stream` |
| Knowledge | `/api/v1/knowledge/bases`, `/api/v1/knowledge/documents/{id}/chunks`, `/api/v1/knowledge/documents/{id}/reindex` |

## Agent Tools

当前 Agent 工具注册在 `backend/app/agent/tools/`：

| Tool | Purpose |
| --- | --- |
| `list_user_jobs` | 查找当前用户岗位，帮助解析“最新岗位”“某公司岗位”等自然语言引用 |
| `list_user_resumes` | 查找当前用户简历 |
| `list_user_applications` | 查找当前用户投递记录 |
| `analyze_match` | 基于岗位和简历生成匹配分析 |
| `generate_cover_letter` | 基于简历、岗位和匹配结果生成求职信 |
| `generate_interview_prep` | 生成中文面试准备提纲 |
| `search_knowledge` | 在当前用户知识库中执行可配置 RAG 检索 |
| `generate_tailored_resume` | 生成针对岗位的定制简历版本 |
| `draft_job` | 把用户在对话里贴的 JD 文本或岗位 URL 起草为岗位草稿（不落库） |
| `draft_resume` | 把用户在对话里贴的简历文本起草为简历草稿（不落库） |
| `create_job` | 用户确认草稿后落库岗位；支持携带 `parsed_json` 一次写入 |
| `create_resume` | 用户确认草稿后落库简历；`content_hash` 由服务端计算 |
| `read_resume` | 按 id 读取一份简历完整结构（含 `parsed_json` + `raw_text`） |
| `read_job_posting` | 按 id 读取一份岗位完整结构（含 `parsed_json` + `jd_text`） |
| `parse_resume` | 对一份已落库但未解析的简历触发 LLM 解析，把 `parse_status` 升级为 parsed |
| `parse_job_posting` | 对一份已落库但未解析的岗位触发 LLM 解析，填充 `parsed_json` |
| `create_application` | 创建投递记录，把指定简历和岗位绑定起来 |
| `update_application_stage` | 推进投递阶段并写一条 `stage_changed` 事件（`operator_type=assistant`） |
| `list_generated_artifacts` | 列出已生成的求职信 / 面试材料等（紧凑列表，不返回正文） |
| `add_knowledge_text` | 把文本作为新文档保存到指定知识库（**仅在用户明确要求保存时调用**） |

## Development Commands

Backend tests:

```powershell
uv --cache-dir .uv-cache --directory backend run pytest
```

Agent eval（行为回归框架，跟 pytest 互补，默认 fake LLM 不耗 token）：

```powershell
uv --cache-dir .uv-cache --directory backend run python -m app.eval.cli
```

详细见 [backend/README.md#agent-eval](backend/README.md#agent-eval)。

Base / LoRA 的纯 Agent 控制变量实验使用请求级工具隔离，不需要停止 RAG 服务；
完整命令和指标说明见 [Base / LoRA 无 RAG Agent 对比](backend/README.md#base--lora-无-rag-agent-对比)。

500 条独立领域问题经完整 LangGraph 的配对评测见
[evaluation/agent/README.md](evaluation/agent/README.md)。

Frontend build:

```powershell
cd frontend
npm run build
```

GitHub Actions 会在 push / pull request 时运行后端 pytest 和前端 production build；配置见 `.github/workflows/ci.yml`。

Database migration:

```powershell
uv --cache-dir .uv-cache --directory backend run alembic upgrade head
```

Stop local services:

```powershell
docker compose down
```

Stop and remove local data volumes:

```powershell
docker compose down -v
```

## License

JobPilot is released under the [MIT License](LICENSE).
