# JobPilot Frontend

`frontend/` 是 JobPilot 第 16 步初始化的前端骨架。它的目标不是一次性完成完整产品，也不是做一个普通 CRUD 管理台或单聊天框，而是先把 `project_v2.md` 中的双层结构落成可运行的页面和路由：

- Workflow Workspace：工作台、岗位 JD、简历、匹配分析、AI 材料、投递跟踪
- AI Copilot Layer：AI 助手、知识库 / 检索增强入口

## 技术栈

- Vue 3
- Vite
- TypeScript
- Vue Router
- Axios
- Element Plus

当前阶段没有引入 Pinia、SSR、Tailwind、测试框架、登录权限、聊天 SDK、RAG SDK 或复杂工程化体系。

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
VITE_API_BASE_URL=http://localhost:8000
```

## 页面结构

- `/`：Dashboard，展示 JobPilot 主流程和双层产品结构
- `/jobs`：JobPosting 页面骨架，对齐 `GET /api/v1/jobs` 和 `POST /api/v1/jobs/{job_id}/parse`
- `/resumes`：Resume / ResumeVersion 页面骨架，对齐简历列表、解析和版本列表入口
- `/matches`：MatchResult 页面骨架，对齐匹配列表和 `POST /api/v1/matches/analyze`
- `/artifacts`：GeneratedArtifact 页面骨架，对齐材料生成和 feedback 记录入口
- `/applications`：ApplicationRecord / ApplicationEvent 页面骨架，对齐投递列表、阶段流转和事件列表
- `/assistant`：AI Copilot Layer 静态壳子，预留场景入口、对话区和上下文挂载区
- `/knowledge`：知识库 / RAG 入口壳子，预留私有知识、通用知识和检索增强说明

## 当前已封装的 API

API client 位于 `src/api/client.ts`，通过 `VITE_API_BASE_URL` 配置后端地址。当前轻量封装了近期会接入页面的真实接口：

- `GET /api/v1/jobs`
- `GET /api/v1/resumes`
- `GET /api/v1/matches`
- `GET /api/v1/artifacts`
- `GET /api/v1/applications`
- `POST /api/v1/jobs/{job_id}/parse`
- `POST /api/v1/resumes/{resume_id}/parse`
- `POST /api/v1/matches/analyze`
- `POST /api/v1/artifacts/generate-cover-letter`
- `POST /api/v1/artifacts/generate-interview-prep`
- `POST /api/v1/applications/{application_id}/transition`
- `GET /api/v1/applications/{application_id}/events`
- `GET /api/v1/artifacts/{artifact_id}/feedback`
- `POST /api/v1/artifacts/{artifact_id}/feedback`

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

本阶段只建立可运行、可讲解的前端骨架。当前不实现完整列表、详情、创建、编辑、认证、真实聊天、SSE / WebSocket、LangChain / LangGraph、RAG、知识库上传、向量检索、反馈聚合或评测中心。
