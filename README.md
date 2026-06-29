# JobPilot

JobPilot 是面向求职者的 AI Copilot。它把岗位收集、简历管理、匹配分析、求职材料生成、模拟面试、知识库检索和投递跟进放进同一条工作流，帮助用户从看到一个岗位一路推进到定制材料、准备面试和持续跟进。

当前项目已经完成核心 MVP 闭环，并进入 Agent + RAG 产品化阶段：后端有真实的 FastAPI API、LangGraph 工作流、OpenAI-compatible LLM / Embedding client、PostgreSQL + pgvector 检索层；前端有 Vue 3 + Element Plus 的求职工作台、SSE 流式 AI 助手、知识库管理和多类材料生成入口。

## Architecture

### Core Flow

下面展示从 Vue WebUI 发起请求，经 FastAPI、AssistantService、LangGraph 工作流与工具调用，到 SSE 响应和 PostgreSQL / pgvector 持久化的核心链路。

<p align="center">
  <img src="docs/images/readme/jobpilot-core-flow.svg" alt="JobPilot Core Flow 核心流程图" width="100%" />
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
- RAG 知识库：支持资料上传、手工文本、切片、embedding、pgvector 检索和 chunk 预览。
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
| RAG 检索 | Agent 工具 `search_knowledge` 使用 pgvector 在当前用户知识库内检索资料 |

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

AUTH_SECRET_KEY=change-this-to-a-long-random-secret
AUTH_DEV_MODE=true
```

Embedding 配置可以独立指定；如果未设置 `EMBEDDING_*`，客户端会在运行时尝试复用对应的 `LLM_*` 配置。不同 embedding 维度需要数据库迁移配合，默认维度为 1536。

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
| `search_knowledge` | 在当前用户知识库中做语义检索 |
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
