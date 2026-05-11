# JobPilot Frontend

`frontend/` 是 JobPilot 的 Vue 3 前端应用。本次产品化重构一期把页面从“后端资源管理台”收敛为求职者视角的个人求职 Copilot。当前前端已经承载核心求职 workflow，下一阶段会把 AI 助手从产品壳接入真实 Agent 后端：

- 首页：我的求职状态、今日建议动作和最近工作
- 简历管理：管理简历原文、AI 提取信息和版本记录
- 岗位管理：保存岗位链接、JD 原文和 AI 解析结果
- 岗位与简历匹配度：选择岗位和简历，分析匹配度，并生成求职信或面试准备
- 投递跟进：管理投递阶段、下一步动作、投递网址和时间线
- AI 助手：按岗位、简历、投递记录和知识库设置上下文；当前为产品壳，后续接入 `/assistant/run`、Conversation / Message 和 AgentRun 状态
- 知识库管理：管理资料与知识库入口；当前为产品壳，后续接入 LangChain + pgvector RAG 知识库

`/artifacts` 历史材料页仍保留为隐藏详情路由，但材料生成的主入口已经聚合到“岗位与简历匹配度”页面。

## 技术栈

- Vue 3
- Vite
- TypeScript
- Vue Router
- Axios
- Element Plus

当前阶段没有引入 Pinia、SSR、Tailwind、测试框架、登录权限、聊天 SDK、RAG SDK 或复杂工程化体系。下一阶段前端会优先接真实 AI Copilot 后端，不会先引入复杂前端状态管理。

## 最小用户切换

当前保留一个 dev-only 的最小用户切换机制：

- 侧边栏和 Header 展示用户区，看起来像真实软件里的当前用户状态
- Header 用户菜单中可在 `demo` 和 `sandbox` 之间切换当前用户
- 这不是正式认证系统，也不代表已经有注册登录能力
- `test` 用户只用于 pytest 数据隔离，不作为正常演示用户暴露在 UI

当前用户值保存在浏览器本地，并由统一 API client 为每次请求附加 `X-User-Name` header。

## 产品化重构一期

本次仍然只做轻量前端产品化整改：

- 左侧导航固定为 7 个面向用户任务的一级入口
- 首页从“系统说明台”调整为“我的求职状态”
- 简历、岗位、投递页去掉大量说明卡片，保留列表、详情、创建和真实操作
- 匹配页成为核心链路：岗位 + 简历 → 匹配分析 → 求职材料生成
- AI 助手重做为对话历史、聊天区和上下文设置三栏结构
- 知识库管理重做为知识库列表、详情和文档入口
- 本次不改后端、不新增 migration，也不接真实 Agent / RAG / 上传

## 下一阶段 AI Copilot 前端方向

前端下一阶段目标不是做假聊天，而是接入后端真实 Agent Runtime：

```text
用户选择岗位 / 简历 / 投递记录 / 知识库
↓
前端创建或选择 conversation
↓
发送用户请求到 POST /api/v1/assistant/run
↓
后端执行 LangGraph workflow
↓
前端展示 user message、assistant message、生成的 artifact 或错误状态
↓
用户可继续追问，或对回复进行 feedback
```

优先接入的界面能力：

- 会话列表：加载 `Conversation`，支持新建对话和切换对话。
- 消息流：展示 `Message` 历史、运行中状态和失败提示。
- 上下文面板：继续保留岗位、简历、投递记录、知识库选择。
- Agent 结果展示：区分普通回复、结构化建议和生成的求职材料。
- 运行可观测入口：后续可在开发模式下展示 `AgentRun` 和 `ToolCallLog` 摘要。

## 启动方式

```powershell
cd frontend
npm install
npm run dev
```

构建验证：

```powershell
npm run build
```

## 环境变量

复制 `.env.example` 为 `.env` 后可调整 API 地址：

```powershell
VITE_API_BASE_URL=/
VITE_API_TIMEOUT_MS=30000
```

开发环境默认推荐使用同源代理：`npm run dev` 时，Vite 会把 `/api` 和 `/health` 转发到 `http://localhost:8000`，这样不需要改后端 CORS 配置。若后续已有同源网关或后端开启了跨域，也仍然支持把 `VITE_API_BASE_URL` 改成完整地址，例如 `http://localhost:8000`。

## 页面结构

- `/`：首页，真实加载最近岗位、简历、匹配、材料和投递摘要，展示今日建议动作与最近工作
- `/resumes`：简历管理，真实接入列表、详情、创建、`POST /api/v1/resumes/{resume_id}/parse` 和 ResumeVersion 只读列表
- `/jobs`：岗位管理，真实接入列表、详情、创建和 `POST /api/v1/jobs/{job_id}/parse`
- `/matches`：岗位与简历匹配度，真实接入列表、详情、`POST /api/v1/matches/analyze`，并聚合 Cover Letter / Interview Prep 生成
- `/applications`：投递跟进，真实接入列表、阶段筛选、详情、创建、transition 与事件时间线
- `/assistant`：AI 助手产品壳，包含对话模板、聊天区、快捷问题和上下文选择；下一阶段接真实 Agent Runtime
- `/knowledge`：知识库管理产品壳，包含知识库列表、文档入口和 AI 助手入口；下一阶段接真实保存、切块、索引和资料引用
- `/artifacts`：历史求职材料详情路由，保留真实 GeneratedArtifact 列表、详情、反馈能力，但不再作为一级导航入口

## 当前已封装的 API

API client 位于 `src/api/client.ts`，通过 `VITE_API_BASE_URL` 配置后端地址。当前轻量封装了近期会接入页面的真实接口：

- `GET /api/v1/jobs`
- `GET /api/v1/resumes`
- `GET /api/v1/matches`
- `GET /api/v1/artifacts`
- `GET /api/v1/artifacts/{artifact_id}`
- `GET /api/v1/applications`
- `GET /api/v1/applications/{application_id}`
- `POST /api/v1/jobs/{job_id}/parse`
- `POST /api/v1/resumes/{resume_id}/parse`
- `POST /api/v1/matches/analyze`
- `POST /api/v1/artifacts/generate-cover-letter`
- `POST /api/v1/artifacts/generate-interview-prep`
- `POST /api/v1/applications`
- `POST /api/v1/applications/{application_id}/transition`
- `GET /api/v1/applications/{application_id}/events`
- `GET /api/v1/artifacts/{artifact_id}/feedback`
- `POST /api/v1/artifacts/{artifact_id}/feedback`

当前已经真正接到页面的能力：

- 首页：真实加载最近 JobPosting / Resume / MatchResult / GeneratedArtifact / ApplicationRecord
- 岗位管理：列表加载、选中查看详情、创建 JobPosting、触发 JD parse
- 简历管理：列表加载、选中查看详情、创建 Resume、自动计算 `content_hash`、触发 Resume parse、查看 ResumeVersion 只读列表
- 岗位与简历匹配度：列表加载、选中查看详情、复用 Resume / JobPosting 选项发起 analyze，生成 Cover Letter 与 Interview Prep
- 投递跟进：列表加载、阶段筛选、选中查看详情、创建 ApplicationRecord、查看 ApplicationEvent 时间线、执行 transition 并刷新详情与列表
- 历史材料页：列表加载、选中查看详情、查看 feedback 历史、提交 ArtifactFeedback
- AI 助手：产品壳，不接真实发送、历史持久化或 Agent Runtime；后续前端主任务是接 `/assistant/run`
- 知识库管理：产品壳，不接真实上传、保存、索引或资料引用；后续接 KnowledgeBase / Document / Chunk API

这些页面共享同一个最小用户 header 机制；切换 `demo / sandbox` 后，页面会重新加载当前用户作用域下的数据。

下一阶段计划封装的 API：

- `GET /api/v1/conversations`
- `POST /api/v1/conversations`
- `GET /api/v1/conversations/{conversation_id}/messages`
- `POST /api/v1/assistant/run`
- `GET /api/v1/agent-runs/{agent_run_id}`
- `GET /api/v1/agent-runs/{agent_run_id}/tool-calls`
- `GET /api/v1/knowledge-bases`
- `POST /api/v1/knowledge-bases`
- `POST /api/v1/knowledge-documents`
- `POST /api/v1/agent-feedback`

## 当前完成度口径

| 模块 | 完成度估算 |
| --- | ---: |
| 前端页面结构 / 导航 / 产品表达 | 70%-75% |
| 核心 workflow 页面真实接入 | 65%-70% |
| AI 助手真实对话 | 0%-10% |
| 知识库真实保存与 RAG 引用 | 0%-10% |
| 运行日志 / 评估界面 | 0%-10% |

## 类型对齐

`src/types/` 直接对齐当前后端 schema 命名，保留以下核心概念：

- `JobPosting`
- `Resume`
- `MatchResult`
- `GeneratedArtifact`
- `ApplicationRecord`
- `ResumeVersion`
- `ApplicationEvent`

如果后续发现 `project_v2.md` 的概念与后端资源命名不完全一致，前端优先使用当前已经存在的后端模型和 API 命名。

## 当前边界

本阶段仍然不实现正式认证、真实聊天、SSE / WebSocket、LangChain / LangGraph、RAG、知识库上传、向量检索、反馈聚合或评测中心。已有的岗位、简历、匹配、材料、投递真实闭环会继续保留；AI 助手和知识库管理当前只做产品结构和入口。下一阶段会优先把 AI 助手接入真实 Agent 后端，再逐步补知识库 RAG 和评估界面。
