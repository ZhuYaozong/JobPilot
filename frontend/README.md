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

## 最小用户切换

第 24 步新增了一个 dev-only 的最小用户切换机制：

- Header 右上角可在 `demo` 和 `sandbox` 之间切换当前用户
- 这不是正式认证系统，也不代表已经有注册登录能力
- `test` 用户只用于 pytest 数据隔离，不作为正常演示用户暴露在 UI

当前用户值保存在浏览器本地，并由统一 API client 为每次请求附加 `X-User-Name` header。

## 第 25 步前端收口

第 25 步只做纯前端整改：

- 主要页面的用户可见文案已经统一为中文优先，英文术语只保留为辅助信息
- Jobs / Resumes / Matches / Artifacts / Applications 左侧列表区已做受控高度与内部滚动治理
- 这一步不再改后端用户作用域、数据模型、schema、API 或测试

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

- `/`：Dashboard 真实工作台首页，展示主流程、最近记录概览、下一步建议与 Workflow Workspace / AI Copilot Layer 入口
- `/jobs`：JobPosting 真实闭环，已接入列表、详情、创建和 `POST /api/v1/jobs/{job_id}/parse`
- `/resumes`：Resume 真实闭环，已接入列表、详情、创建、`POST /api/v1/resumes/{resume_id}/parse` 和 ResumeVersion 只读列表
- `/matches`：MatchResult 真实闭环，已接入列表、详情和 `POST /api/v1/matches/analyze`
- `/artifacts`：GeneratedArtifact 真实闭环，已接入列表、详情、Cover Letter / Interview Prep 生成、feedback 历史查看与 feedback 提交
- `/applications`：ApplicationRecord / ApplicationEvent 真实闭环，已接入列表、详情、创建、transition 与事件时间线
- `/assistant`：AI 助手高保真产品壳，已升级为三栏 Copilot 工作区，展示推荐场景、会话预览、对话壳、上下文插槽、工具预览与 Knowledge 入口，但尚未接真实 Agent Runtime
- `/knowledge`：知识库 / RAG 入口壳，已升级为多区知识工作台，展示私有知识、通用知识、检索流程、上下文注入、引用意识与 Assistant 协同关系，但尚未接真实检索运行时

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

- Dashboard 首页：真实加载最近 JobPosting / Resume / MatchResult / GeneratedArtifact / ApplicationRecord，展示轻量下一步建议与模块入口
- Jobs 页面：列表加载、选中查看详情、创建 JobPosting、触发 JD parse
- Resumes 页面：列表加载、选中查看详情、创建 Resume、自动计算 `content_hash`、触发 Resume parse、查看 ResumeVersion 只读列表
- Matches 页面：列表加载、选中查看详情、复用 Resume / JobPosting 选项发起 analyze，并在成功后自动刷新选中新结果
- Artifacts 页面：列表加载、选中查看详情、复用 Resume / JobPosting 选项生成 Cover Letter 与 Interview Prep、查看 feedback 历史、提交 ArtifactFeedback
- Applications 页面：列表加载、选中查看详情、创建 ApplicationRecord、查看 ApplicationEvent 时间线、执行 transition 并刷新详情与列表
- Assistant 页面：高保真 AI Copilot 产品壳，展示推荐场景、Session Preview、中间对话工作区、上下文挂载、Tools Preview 与 Knowledge 入口，并明确当前未接真实 Agent / RAG
- Knowledge 页面：高保真 Knowledge / RAG 入口壳，展示知识源分类、检索增强流程、上下文注入、Citations / Trace 意识、状态面板与 Assistant 协同入口，并明确当前未接真实上传 / 索引 / 检索运行时

第 24 步后，这些页面共享同一个最小用户 header 机制；切换 `demo / sandbox` 后，页面会重新加载当前用户作用域下的数据。第 25 步又进一步把主要页面文案收口为中文优先，并把五个工作页的左侧列表收成统一的受控高度和内部滚动区域。

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
