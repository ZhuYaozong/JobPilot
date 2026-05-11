# JobPilot

JobPilot 是一个面向求职者的个人求职 Copilot。它把岗位收集、简历管理、匹配分析、求职材料生成和投递跟进串成一条清晰的求职工作流，帮助用户从“看到一个岗位”一路推进到“准备材料、投递并持续跟进”。

这个项目不是一个简单的 CRUD 后台，也不是一个空白聊天框。JobPilot 当前已经具备“岗位 - 简历 - 匹配 - 材料 - 投递”的核心 MVP 闭环，下一阶段会从求职工作台升级为带有受控 Agent Workflow、工具调用、RAG 知识库和运行评估的 AI 求职 Copilot。

## 为什么做 JobPilot

求职过程中最容易散掉的不是信息不够，而是信息太分散：

- JD 存在浏览器收藏夹里
- 简历版本散在本地文件夹里
- 匹配度判断靠临时感觉
- 求职信和面试准备每次都从零开始
- 投递之后忘记什么时候该跟进

JobPilot 希望把这些动作收进一个面向求职者的产品里，让 AI 不只是“回答问题”，而是围绕真实的求职对象持续协作。

## 核心能力

- 岗位管理：保存目标岗位、岗位链接和 JD 原文，支持 JD 结构化解析。
- 简历管理：保存简历原文、来源信息和版本记录，支持简历结构化解析。
- 匹配分析：基于已解析的岗位和简历生成匹配度、优势、短板、缺失关键词和修改建议。
- 求职材料生成：基于岗位、简历和匹配结果生成求职信草稿和面试准备提纲。
- 投递跟进：记录投递阶段、渠道、下一步动作、待办时间、备注和阶段流转时间线。
- AI 助手：围绕岗位、简历、投递记录和知识库设置上下文；当前是产品结构，下一阶段接入 Conversation / Message、LangGraph 工作流和真实 Agent 后端。
- 知识库管理：管理公司资料、项目素材、面试资料等 AI 可引用资料入口；当前是产品结构，后续会接入 LangChain + pgvector 的最小 RAG 闭环。

## 产品页面

当前前端已经按求职者任务重构为 7 个一级入口：

| 页面 | 定位 |
| --- | --- |
| 首页 | 查看求职状态、今日建议动作和最近工作 |
| 简历管理 | 管理简历原文、AI 提取信息和版本记录 |
| 岗位管理 | 保存目标岗位、岗位链接和 JD 原文 |
| 岗位与简历匹配度 | 选择岗位和简历，分析匹配度，并生成求职材料 |
| 投递跟进 | 管理投递阶段、下一步动作、投递网址和时间线 |
| AI 助手 | 选择岗位、简历、投递记录和知识库作为对话上下文 |
| 知识库管理 | 管理资料和知识库入口，供后续 AI 引用 |

`/artifacts` 仍保留为历史求职材料详情页，但不再作为一级导航入口；材料生成主链路已经聚合到“岗位与简历匹配度”页面。

## 下一阶段 Agent Workflow 方向

JobPilot 后续 AI 助手不做“完全自由聊天机器人”，而是做一个可控、可观测、可落库的求职 Agent Workflow：

```text
前端发送 conversation_id / 上下文 id / 用户请求
↓
后端写入 user message，并创建 AgentRun
↓
读取业务数据、历史 messages 和 memory_summary
↓
构造 system prompt、任务规则、工具规则和输出格式
↓
进入 LangGraph Agent Workflow
↓
识别 intent，选择受控 workflow 节点
↓
LangChain StructuredTool + Pydantic 校验工具参数
↓
Tool Adapter 校验用户作用域、业务规则和前置条件
↓
调用真实业务工具、现有 LLM client 或 RAG retriever
↓
记录 ToolCallLog，汇总工具结果
↓
生成最终回复或结构化产物，并做最终 Schema 校验 / repair
↓
写入 assistant message / generated_artifacts，必要时更新 memory_summary
↓
更新 AgentRun 状态，前端展示结果
```

这条路线会保留现有 OpenAI-compatible LLM client 作为模型适配层；LangGraph 只负责流程编排，LangChain StructuredTool 负责工具抽象，核心业务逻辑继续沉在已有 service 和数据库模型里。

## 当前真实接入的闭环

这些能力已经接入后端真实 API：

- 岗位列表、详情、创建、更新、JD 解析
- 简历列表、详情、创建、更新、简历解析
- 简历版本只读列表
- 匹配分析列表、详情、自动生成
- 求职信草稿生成
- 面试准备提纲生成
- AI 产物列表、详情、反馈记录
- 投递记录列表、详情、创建、更新
- 投递阶段流转与事件时间线
- dev-only 用户作用域隔离，基于 `X-User-Name`

当前还没有伪造成熟能力：

- AI 助手还没有真实 Conversation / Message 后端
- 还没有 Tool Adapter、LangChain StructuredTool 或 LangGraph Agent Workflow
- 还没有 AgentRun / ToolCallLog 运行追踪
- 知识库还没有真实上传、保存、索引或 RAG 检索
- 还没有 Eval / Feedback / Agent 质量评估闭环
- 没有正式登录认证系统
- 没有文件上传、对象存储或导出 PDF/DOCX
- 没有异步任务编排或生产级队列

## 技术栈

### Frontend

- Vue 3
- Vite
- TypeScript
- Vue Router
- Axios
- Element Plus

### Backend

- FastAPI
- SQLAlchemy async
- Alembic
- PostgreSQL
- Redis
- uv
- OpenAI-compatible Chat Completions API

### Planned AI Workflow

- LangChain StructuredTool
- LangGraph
- PostgreSQL + pgvector RAG
- AgentRun / ToolCallLog observability
- Eval / Feedback quality loop

### Infrastructure

- Docker Compose
- PostgreSQL + pgvector extension
- Redis

## 系统结构

```text
JobPilot/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routers
│   │   ├── models/       # SQLAlchemy models
│   │   ├── schemas/      # Pydantic schemas
│   │   ├── services/     # Parsing / generation / workflow services
│   │   ├── llm/          # OpenAI-compatible LLM client
│   │   └── db/
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

下一阶段计划在 `backend/app/` 下新增 `agent/` 模块，用于承载 LangGraph workflow、LangChain StructuredTool registry、Tool Adapter、AgentRun / ToolCallLog 相关逻辑。

## 快速开始

### 1. 启动基础设施

```powershell
docker compose up -d
```

默认会启动：

- PostgreSQL：`localhost:25432`
- Redis：`localhost:26379`

### 2. 配置后端环境变量

复制环境变量示例：

```powershell
Copy-Item .env.example .env
Copy-Item backend/.env.example backend/.env
```

AI 相关能力使用 OpenAI-compatible Chat Completions 接口：

```powershell
LLM_BASE_URL=https://api.example.com/v1
LLM_API_KEY=your-api-key
LLM_MODEL_NAME=your-model-name
```

如果没有配置 LLM，解析和生成接口会返回清晰错误，不会伪造成功结果。

### 3. 执行数据库迁移

```powershell
uv --cache-dir .uv-cache --directory backend run alembic upgrade head
```

### 4. 启动后端

```powershell
uv --cache-dir .uv-cache --directory backend run uvicorn app.main:app --reload
```

后端默认地址：

```text
http://localhost:8000
```

健康检查：

```text
GET /health
GET /health/db
```

### 5. 启动前端

```powershell
cd frontend
npm install
npm run dev
```

前端默认地址：

```text
http://localhost:5173
```

## 常用命令

前端构建：

```powershell
cd frontend
npm run build
```

后端测试：

```powershell
uv --cache-dir .uv-cache --directory backend run pytest
```

数据库迁移：

```powershell
uv --cache-dir .uv-cache --directory backend run alembic upgrade head
```

停止本地服务：

```powershell
docker compose down
```

停止并清理本地数据卷：

```powershell
docker compose down -v
```

## API 概览

核心 API 均挂载在 `/api/v1` 下：

| 模块 | API |
| --- | --- |
| 简历 | `/api/v1/resumes` |
| 简历版本 | `/api/v1/resume-versions` |
| 岗位 | `/api/v1/jobs` |
| 匹配分析 | `/api/v1/matches` |
| 投递记录 | `/api/v1/applications` |
| 求职材料 | `/api/v1/artifacts` |
| 材料反馈 | `/api/v1/artifacts/{artifact_id}/feedback` |

主要 AI / workflow 动作：

```text
POST /api/v1/jobs/{job_id}/parse
POST /api/v1/resumes/{resume_id}/parse
POST /api/v1/matches/analyze
POST /api/v1/artifacts/generate-cover-letter
POST /api/v1/artifacts/generate-interview-prep
POST /api/v1/applications/{application_id}/transition
```

## 当前状态

JobPilot 当前处于“核心 workflow MVP 完成，Agent 化升级前”的阶段：

- 前端已经从开发者资源后台重构为求职者视角的软件界面。
- 后端核心 workflow 和 AI 生成闭环已经可用。
- 自动化测试覆盖核心后端能力。
- AI 助手和知识库管理还处于产品壳阶段，没有伪造成熟聊天或 RAG。

按完整产品愿景估算：

| 口径 | 当前完成度 |
| --- | ---: |
| 可演示 MVP | 65%-70% |
| 可长期使用的个人求职 Copilot | 40%-45% |
| 企业级 Agent Workflow / RAG / 评估体系 | 10%-15% |

最近一次验证结果：

```text
frontend npm run build: passed
backend pytest: 64 passed
```

## Roadmap

下一阶段主线：

1. Conversation / Message 最小数据模型。
2. Tool Adapter + LangChain StructuredTool 封装已有能力。
3. LangGraph 最小求职工作流 + `/assistant/run` 后端接口。
4. AgentRun / ToolCallLog 最小运行日志。
5. 前端 AI Copilot 接真实 Agent 后端。
6. LangChain + pgvector RAG 知识库最小闭环。
7. KnowledgeRetriever Tool 接入 LangGraph。
8. Eval / Feedback / Agent 质量评估。

并行的小改进：

- 给投递记录补充独立 `application_url` 字段。
- 支持从岗位页、简历页跳转到匹配页时自动预选上下文。
- 支持求职材料导出。
- 增加投递提醒和日程视图。
- 增加更完整的用户认证和权限模型。
- 优化前端代码分包，降低生产构建 chunk size。

## 项目边界

JobPilot 当前更关注“求职流程是否跑得通”和“产品表达是否像给求职者使用的软件”。下一阶段会引入 LangChain / LangGraph / RAG，但仍会保持一个边界：框架只做工具抽象、流程编排和检索增强，不替代核心业务 service、数据库约束和用户作用域校验。

如果你关注的是 Agentic Workflow、AI 求职助手、FastAPI + Vue 全栈项目，或者想看一个项目如何从资源管理后台逐步产品化，JobPilot 会是一个很适合继续扩展的基础。
