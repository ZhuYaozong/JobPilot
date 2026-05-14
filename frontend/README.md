# JobPilot Frontend

`frontend/` 是 JobPilot 的 Vue 3 前端应用。它面向求职者组织完整工作流：收集岗位、管理简历、生成匹配分析、产出求职材料、维护知识库、进入 AI 助手和模拟面试，并记录投递进展。

当前前端不再是资源 CRUD 管理台。主要页面已经接入真实后端 API，并通过 SSE 展示 Agent 运行过程。

## Technology

- Vue 3
- Vite
- TypeScript
- Vue Router
- Axios
- Element Plus

当前没有引入 Pinia、SSR、Tailwind 或前端测试框架。跨页面共享状态仍保持轻量，优先通过 API 刷新和局部组件状态完成。

## Local Development

安装依赖：

```powershell
cd frontend
npm install
```

启动开发服务器：

```powershell
npm run dev
```

构建验证：

```powershell
npm run build
```

预览构建产物：

```powershell
npm run preview
```

默认开发地址：

```text
http://localhost:5173
```

## Environment

复制环境变量：

```powershell
Copy-Item .env.example .env
```

配置项：

```env
VITE_API_BASE_URL=/
```

开发环境推荐使用同源代理：Vite 将 `/api` 和 `/health` 转发到本地 FastAPI。若后端已开放 CORS 或部署在单独域名，也可以把 `VITE_API_BASE_URL` 改为完整地址，例如 `http://localhost:8000`。

## User Scope

前端保留一个 dev-only 用户切换机制：

- Header 用户菜单可在 `demo` 和 `sandbox` 之间切换。
- 当前用户保存在浏览器本地。
- API client 为请求自动附加 `X-User-Name`。
- `test` 用户只用于后端自动化测试，不在 UI 中暴露。

这不是正式认证系统，也不代表项目已经支持注册登录。

## Routes

| Route | Page | Current capability |
| --- | --- | --- |
| `/` | 首页 | 加载最近岗位、简历、匹配、材料和投递，展示建议动作 |
| `/jobs` | 岗位管理 | 创建、编辑、删除岗位；从 URL 抓取 JD；触发 JD parse |
| `/resumes` | 简历管理 | 创建、编辑、删除简历；上传 PDF / DOCX / TXT / MD；触发 resume parse；查看版本 |
| `/matches` | 岗位与简历匹配度 | 生成匹配分析、求职信、面试准备和定制简历 |
| `/applications` | 投递跟进 | 创建投递、阶段筛选、详情、transition、事件时间线 |
| `/assistant` | AI 助手 | 流式对话、上下文选择、工具进度、模拟面试模式 |
| `/knowledge` | 知识库管理 | 知识库 CRUD、文档上传/粘贴、重新索引、chunk 预览 |
| `/artifacts` | 求职材料 | 查看历史材料、反馈记录和材料详情 |

## Page Details

### Dashboard

首页从多个业务 API 拉取当前用户最近数据，聚合展示：

- 最近岗位
- 最近简历
- 最近匹配分析
- 最近求职材料
- 最近投递记录
- 今日建议动作

### Jobs

岗位页支持两种录入方式：

- 从 URL 抓取 JD，并在写入前预览和补齐岗位信息。
- 手工录入公司、岗位、城市、来源链接和 JD 原文。

真实接入：

- `GET /api/v1/jobs`
- `POST /api/v1/jobs`
- `PATCH /api/v1/jobs/{job_id}`
- `DELETE /api/v1/jobs/{job_id}`
- `POST /api/v1/jobs/fetch-from-url`
- `POST /api/v1/jobs/{job_id}/parse`

### Resumes

简历页支持：

- 手工创建简历。
- 上传 PDF / DOCX / TXT / MD。
- 查看结构化解析结果。
- 查看简历版本列表。
- 删除简历并刷新相关列表。

真实接入：

- `GET /api/v1/resumes`
- `POST /api/v1/resumes`
- `POST /api/v1/resumes/upload`
- `PATCH /api/v1/resumes/{resume_id}`
- `DELETE /api/v1/resumes/{resume_id}`
- `POST /api/v1/resumes/{resume_id}/parse`
- `GET /api/v1/resumes/{resume_id}/versions`

### Matches

匹配页是材料生成主入口。用户选择一组岗位和简历后，可以：

- 生成匹配分析。
- 生成求职信。
- 生成面试准备。
- 生成定制简历版本。

定制简历请求只传 `resume_id` 和 `job_posting_id`，后端会按当前用户查询这组对象的最新匹配结果；`application_record_id` 不是生成前置条件。

真实接入：

- `GET /api/v1/matches`
- `POST /api/v1/matches/analyze`
- `GET /api/v1/matches/{match_id}`
- `POST /api/v1/artifacts/generate-cover-letter`
- `POST /api/v1/artifacts/generate-interview-prep`
- `POST /api/v1/resume-versions/generate-tailored`

### Applications

投递页支持：

- 创建投递记录。
- 按阶段筛选。
- 查看投递详情。
- 执行阶段流转。
- 查看事件时间线。
- 删除投递记录。

真实接入：

- `GET /api/v1/applications`
- `POST /api/v1/applications`
- `GET /api/v1/applications/{application_id}`
- `PATCH /api/v1/applications/{application_id}`
- `DELETE /api/v1/applications/{application_id}`
- `POST /api/v1/applications/{application_id}/transition`
- `GET /api/v1/applications/{application_id}/events`

### Assistant

AI 助手页已经接入真实后端 Agent：

- Conversation 列表和消息历史。
- 当前上下文选择：岗位、简历、投递记录、知识库。
- `chat` 和 `mock_interview` 两种模式。
- SSE 流式运行状态。
- 工具调用开始和完成提示。
- 错误状态展示。
- 删除会话。

主要调用：

- `GET /api/v1/conversations`
- `GET /api/v1/conversations/{conversation_id}/messages`
- `PATCH /api/v1/conversations/{conversation_id}`
- `DELETE /api/v1/conversations/{conversation_id}`
- `POST /api/v1/assistant/run-stream`
- `POST /api/v1/assistant/run`

前端默认使用 `runAssistantStream`。非流式 `/run` 保留为 fallback 和调试入口。

### Knowledge

知识库页支持：

- 创建、重命名、归档或删除知识库。
- 上传文档。
- 粘贴文本作为知识文档。
- 查看文档状态和错误。
- 重新索引失败或过期文档。
- 查看文档 chunks。

主要调用：

- `GET /api/v1/knowledge/bases`
- `POST /api/v1/knowledge/bases`
- `PATCH /api/v1/knowledge/bases/{kb_id}`
- `DELETE /api/v1/knowledge/bases/{kb_id}`
- `GET /api/v1/knowledge/bases/{kb_id}/documents`
- `POST /api/v1/knowledge/bases/{kb_id}/documents/upload`
- `POST /api/v1/knowledge/bases/{kb_id}/documents`
- `GET /api/v1/knowledge/documents/{document_id}`
- `GET /api/v1/knowledge/documents/{document_id}/chunks`
- `POST /api/v1/knowledge/documents/{document_id}/reindex`
- `DELETE /api/v1/knowledge/documents/{document_id}`

### Artifacts

材料页保留为历史材料和反馈管理入口。匹配页是主要生成入口，材料页负责查看、更新和反馈。

主要调用：

- `GET /api/v1/artifacts`
- `GET /api/v1/artifacts/{artifact_id}`
- `PATCH /api/v1/artifacts/{artifact_id}`
- `DELETE /api/v1/artifacts/{artifact_id}`
- `GET /api/v1/artifacts/{artifact_id}/feedback`
- `POST /api/v1/artifacts/{artifact_id}/feedback`

## API Layer

API 封装位于 `src/api/`：

```text
src/api/
├── applications.ts
├── artifacts.ts
├── assistant.ts
├── client.ts
├── jobs.ts
├── knowledge.ts
├── matches.ts
└── resumes.ts
```

`client.ts` 统一负责：

- `VITE_API_BASE_URL`
- Axios 实例
- `X-User-Name` header
- 常规错误响应
- LLM 长任务 timeout 常量

Assistant SSE 使用 `fetch` 而不是 Axios，因为需要读取 `ReadableStream` 并逐帧解析服务端事件。

## Types

类型定义位于 `src/types/`，与后端 Pydantic schema 对齐：

```text
src/types/
├── application_event.ts
├── application_record.ts
├── assistant.ts
├── common.ts
├── generated_artifact.ts
├── job_posting.ts
├── knowledge.ts
├── match_result.ts
├── resume.ts
└── resume_version.ts
```

重要类型：

- `AssistantRunRequest`
- `AssistantMode`
- `ConversationListItem`
- `MessageRead`
- `KnowledgeBaseListItem`
- `KnowledgeDocumentListItem`
- `KnowledgeChunkPreview`
- `TailoredResumeGenerateRequest`
- `ResumeVersion`

## Build Notes

生产构建命令：

```powershell
npm run build
```

该命令会先运行 `vue-tsc --noEmit` 做类型检查，然后执行 Vite build。当前构建可能出现 Vite chunk size warning，这是前端依赖和页面体量带来的已知提示，不代表构建失败。

## Current Boundaries

前端当前仍不包含：

- 正式登录、注册和权限页面。
- 前端测试框架。
- SSR。
- 离线缓存。
- WebSocket。
- PDF / DOCX 导出界面。
- AgentRun / ToolCallLog 的完整可观测控制台。

这些能力会随后端能力稳定后逐步补齐。当前前端重点是让求职主链路和真实 Agent / RAG 能力清晰、可用、可验证。
