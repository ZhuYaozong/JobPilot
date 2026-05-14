# JobPilot

JobPilot 是面向求职者的 AI Copilot。它把岗位收集、简历管理、匹配分析、求职材料生成、模拟面试、知识库检索和投递跟进放进同一条工作流，帮助用户从看到一个岗位一路推进到定制材料、准备面试和持续跟进。

当前项目已经完成核心 MVP 闭环，并进入 Agent + RAG 产品化阶段：后端有真实的 FastAPI API、LangGraph 工作流、OpenAI-compatible LLM / Embedding client、PostgreSQL + pgvector 检索层；前端有 Vue 3 + Element Plus 的求职工作台、SSE 流式 AI 助手、知识库管理和多类材料生成入口。

## Highlights

- 求职工作台：岗位、简历、匹配、材料、投递、AI 助手、知识库七个核心入口。
- 真实 AI 工作流：解析 JD / 简历，生成匹配分析、求职信、面试准备和定制简历。
- Agent Runtime：基于 LangGraph 1.x 的多节点工作流，支持工具调用、运行记录和 SSE 流式返回。
- RAG 知识库：支持资料上传、手工文本、切片、embedding、pgvector 检索和 chunk 预览。
- 交互式模拟面试：基于当前岗位、简历、匹配结果、interview_prep 和 search_knowledge 逐轮提问。
- 定制简历版本：针对岗位生成 `ai_tailored` 简历版本，保留版本号、来源类型和变更摘要。
- 用户作用域：开发阶段通过 `X-User-Name` 隔离 `demo` / `sandbox` / `test` 用户数据。
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
| 岗位管理 | 创建、编辑、删除岗位；从 URL 抓取 JD 预览；结构化解析 JD |
| 简历管理 | 创建、编辑、删除简历；上传 PDF / DOCX / TXT / MD；结构化解析简历；查看版本 |
| 匹配分析 | 选择岗位和简历生成匹配分、优势、短板、缺失关键词和修改建议 |
| 求职材料 | 生成求职信、面试准备；记录材料反馈；查看历史材料 |
| 定制简历 | 针对岗位生成 `ai_tailored` 简历版本，版本号按 `max(version_no)+1` 递增 |
| 投递跟进 | 创建投递记录、更新阶段、记录下一步动作和阶段事件时间线 |
| AI 助手 | Conversation / Message 持久化，LangGraph 工具调用，SSE 流式进度与回复 |
| 模拟面试 | 在 `mock_interview` 模式下结合岗位、简历、匹配结果、面试准备和知识库逐轮提问 |
| 知识库 | 知识库 CRUD、文档上传/粘贴、同步切片与 embedding、重新索引、chunk 预览 |
| RAG 检索 | Agent 工具 `search_knowledge` 使用 pgvector 在当前用户知识库内检索资料 |

## Screens And Routes

| 路由 | 页面 |
| --- | --- |
| `/` | 首页 |
| `/jobs` | 岗位管理 |
| `/resumes` | 简历管理 |
| `/matches` | 岗位与简历匹配度 |
| `/applications` | 投递跟进 |
| `/assistant` | AI 助手与模拟面试 |
| `/knowledge` | 知识库管理 |
| `/artifacts` | 求职材料历史页 |

## Architecture

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

EMBEDDING_BASE_URL=https://api.example.com/v1
EMBEDDING_API_KEY=your-api-key
EMBEDDING_MODEL_NAME=your-embedding-model
EMBEDDING_DIMENSIONS=1536
```

Embedding 配置可以独立指定；如果未设置 `EMBEDDING_*`，客户端会在运行时尝试复用对应的 `LLM_*` 配置。不同 embedding 维度需要数据库迁移配合，默认维度为 1536。

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

所有业务 API 主要挂载在 `/api/v1` 下：

| Domain | Endpoints |
| --- | --- |
| Resumes | `/api/v1/resumes`, `/api/v1/resumes/upload`, `/api/v1/resumes/{id}/parse` |
| Resume Versions | `/api/v1/resume-versions`, `/api/v1/resume-versions/generate-tailored` |
| Jobs | `/api/v1/jobs`, `/api/v1/jobs/fetch-from-url`, `/api/v1/jobs/{id}/parse` |
| Matches | `/api/v1/matches`, `/api/v1/matches/analyze` |
| Applications | `/api/v1/applications`, `/api/v1/applications/{id}/transition`, `/api/v1/applications/{id}/events` |
| Artifacts | `/api/v1/artifacts`, `/api/v1/artifacts/generate-cover-letter`, `/api/v1/artifacts/generate-interview-prep` |
| Conversations | `/api/v1/conversations`, `/api/v1/conversations/{id}/messages` |
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
| `search_knowledge` | 在当前用户知识库中做语义检索 |
| `generate_tailored_resume` | 生成针对岗位的定制简历版本 |

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

Frontend build:

```powershell
cd frontend
npm run build
```

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

## Current Status

截至切片 7'e，当前主线已合入：

- 基础数据层、用户作用域、recent-first list 规则
- Tool Adapter、LangGraph 三节点工作流、多工具 ReAct 循环
- 产品化 AI Assistant、Conversation / Message / AgentRun / ToolCallLog
- SSE 流式 Assistant，修复长任务 30s 超时问题
- 简历文件上传：PDF / DOCX / TXT / MD
- 岗位 URL 抓取：trafilatura 抽取 + 前端预览确认
- RAG 数据层：KnowledgeBase / KnowledgeDocument / KnowledgeChunk
- 自研文本切片 + OpenAI-compatible embedding + pgvector 索引状态机
- `search_knowledge` tool 与 Agent 集成
- Assistant 可选择知识库，文档 chunks 可预览
- 交互式模拟面试：基于 `search_knowledge` + `interview_prep`
- 定制简历生成：针对岗位生成简历变体

最近一次合入前验证：

```text
backend pytest: passed
frontend npm run build: passed
```

## Known Boundaries

JobPilot 仍然是开发阶段项目，以下能力没有被包装成已完成：

- 没有正式注册、登录、JWT、团队空间或企业级权限。
- 知识库索引当前是请求内同步执行，还没有生产级异步队列。
- 没有 PDF / DOCX 导出和模板排版系统。
- 没有生产级通知、日历提醒或邮件投递集成。
- 没有完整 CI/CD 发布流水线。
- 没有并发安全的简历版本唯一约束；定制简历版本号当前按 `max(version_no)+1` 生成。

## Roadmap

- 将知识库索引从同步请求演进为后台任务。
- 为 AgentRun / ToolCallLog 增加更完整的前端可观测界面。
- 支持求职材料导出 PDF / DOCX。
- 为定制简历版本增加并发锁或唯一约束。
- 增加正式认证和更完整的权限模型。
- 扩展 Agent 质量评估和反馈分析。

## License

当前仓库尚未声明开源许可证。对外使用前请先补充明确的 `LICENSE` 文件。
