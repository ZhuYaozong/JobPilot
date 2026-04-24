# JobPilot

JobPilot 是一个面向求职场景的 Agentic AI Workflow 系统。当前已经完成本地基础设施、后端 FastAPI 骨架、SQLAlchemy async、Alembic、Resume / JobPosting / MatchResult / ApplicationRecord 四个核心模块的最小 API 闭环、workflow 状态层、AI 产物承载层，以及 JD 结构化解析、Resume 结构化解析、MatchResult 自动生成、Cover Letter 草稿生成、Interview Prep 生成和 AI 产物反馈记录能力。第 16 步新增了 `frontend/` Vue 3 前端骨架，用于承接 Workflow Workspace 和 AI Copilot Layer 的页面与路由入口。第 24 步进一步补上了最小用户隔离、pytest 数据隔离，以及 recent-first / limit 规则显式化。第 25 步继续做纯前端收口：主要页面文案中文化，以及工作页左侧列表区的受控高度与内部滚动治理。

第 8 步新增了工作流承载层第一阶段能力：

- 简历版本管理：`ResumeVersion`
- 投递状态流转记录：`ApplicationEvent`
- 投递状态流转动作：`POST /api/v1/applications/{application_id}/transition`

第 8.5 步新增了最小自动化测试底座，当前只覆盖关键 workflow 闭环，不代表完整测试体系。

第 9 步新增了 AI 产物承载层 `GeneratedArtifact`，用于保存手工写入或未来 AI 生成的求职材料产物；当前仍未接入真实 AI 生成。

第 10 步新增了第一个真实 AI 能力：JD 结构化解析。它通过一个很薄的 LLM 接入层解析 `job_postings.jd_text`，并把结构化结果写回 `job_postings.parsed_json`。

第 11 步新增了第二个真实 AI 能力：Resume 结构化解析。它复用同一个很薄的 LLM 接入层解析 `resumes.raw_text`，并把结构化结果写回 `resumes.parsed_json`，同时将 `resumes.parse_status` 更新为 `parsed`。

第 12 步新增了第三个真实 AI 能力：基于结构化 Resume + 结构化 JD 自动生成 MatchResult。它读取 `resumes.parsed_json` 和 `job_postings.parsed_json`，调用同一个 LLM 接入层生成结构化匹配分析，并新增一条 `match_results` 记录。

第 13 步新增了第一类生成能力：Cover Letter 草稿生成。它读取结构化 Resume、结构化 JD 和最近一条 MatchResult，调用同一个 LLM 接入层生成求职信草稿，并新增一条 `generated_artifacts` 记录。

第 14 步新增了第二类生成能力：Interview Prep 生成。它读取结构化 Resume、结构化 JD 和最近一条 MatchResult，调用同一个 LLM 接入层生成中文面试准备提纲，并新增一条 `generated_artifacts` 记录。

第 15 步新增了最小 feedback 闭环：记录用户对 `GeneratedArtifact` 的采纳、编辑后采用、拒绝或稍后保存反馈。当前 feedback 只是事件记录层，不代表完整评测系统，也不会自动修改 artifact 状态或触发重新生成。

第 16 步初始化了前端骨架：Vue 3 + Vite + TypeScript + Vue Router + Axios + Element Plus。当前 frontend 处于可运行的页面骨架阶段，包含工作台、岗位 JD、简历、匹配分析、AI 材料、投递跟踪、AI 助手和知识库入口，但还没有接入完整业务页面、真实聊天 Agent、RAG 或复杂状态管理。

第 17 步完成了第一个真实前端业务闭环：`/jobs` 与 `/resumes` 已接入后端真实 API，支持列表加载、详情查看、创建记录、触发 parse；其中 `/resumes` 额外接入了 ResumeVersion 只读列表，并在前端自动计算 `content_hash`。

第 18 步继续推进前端工作流闭环：`/matches` 已接入后端真实 MatchResult API，支持列表加载、详情查看，以及选择 Resume + JobPosting 发起 analyze，并在成功后自动刷新和选中新生成结果。

当前后端已支持：

- 健康检查：`GET /health`、`GET /health/db`
- 简历模块：`/api/v1/resumes`
- 岗位模块：`/api/v1/jobs`
- 匹配结果模块：`/api/v1/matches`
- 投递记录模块：`/api/v1/applications`
- 简历版本模块：`/api/v1/resume-versions`
- 简历下的版本列表：`GET /api/v1/resumes/{resume_id}/versions`
- 投递事件列表：`GET /api/v1/applications/{application_id}/events`
- 投递阶段流转：`POST /api/v1/applications/{application_id}/transition`
- AI 产物承载模块：`/api/v1/artifacts`
- JD 结构化解析：`POST /api/v1/jobs/{job_id}/parse`
- Resume 结构化解析：`POST /api/v1/resumes/{resume_id}/parse`
- MatchResult 自动生成：`POST /api/v1/matches/analyze`
- Cover Letter 草稿生成：`POST /api/v1/artifacts/generate-cover-letter`
- Interview Prep 生成：`POST /api/v1/artifacts/generate-interview-prep`
- AI 产物反馈创建：`POST /api/v1/artifacts/{artifact_id}/feedback`
- AI 产物反馈列表：`GET /api/v1/artifacts/{artifact_id}/feedback`

第 24 步后，核心业务对象都带有最小用户作用域。当前用户通过 dev-only `X-User-Name` header 确定；未显式传入时默认使用 `demo`。frontend 也提供了最小的 `demo / sandbox` 切换器，但这不是正式登录系统。

核心 list 接口的默认 recent-first 规则也已显式化：

- jobs / resumes / applications：按 `updated_at DESC`
- matches / artifacts：按 `created_at DESC`
- 所有核心 list 接口默认 `limit=20`，并支持 `offset`

当前仍然保持阶段边界：不包含认证登录、RAG、LangChain、LangGraph、自动提醒、复杂状态机、文件上传、Redis 业务逻辑或生产部署配置；frontend 仅为第 16 步产品骨架，不代表完整前端业务闭环。

## 目录结构

```text
JobPilot/
├── backend/
│   ├── app/
│   ├── alembic/
│   ├── tests/
│   ├── README.md
│   └── pyproject.toml
├── docs/
├── frontend/
│   ├── src/
│   ├── README.md
│   ├── package.json
│   └── vite.config.ts
├── infra/
│   └── postgres/
│       └── init/
│           └── 001_extensions.sql
├── .env.example
├── .gitignore
├── AGENTS.md
├── compose.yaml
├── project_v2.md
└── README.md
```

## 启动本地服务

```powershell
docker compose up -d
```

后端启动方式：

```powershell
uv --cache-dir .uv-cache --directory backend run uvicorn app.main:app --reload
```

执行数据库迁移：

```powershell
uv --cache-dir .uv-cache --directory backend run alembic upgrade head
```

运行最小测试：

```powershell
uv --cache-dir .uv-cache --directory backend run pytest
```

当前测试会连接后端配置中的 PostgreSQL 数据库，通过 API 创建带 `pytest-jobpilot-*` 标记的前置数据，不依赖数据库里已有的固定记录。JD / Resume 解析、MatchResult 自动生成、Cover Letter 草稿生成和 Interview Prep 生成测试使用 monkeypatch 替代真实 LLM 调用；artifact feedback 测试只验证本地数据库事件记录。

前端启动方式：

```powershell
cd frontend
npm install
npm run dev
```

前端构建验证：

```powershell
cd frontend
npm run build
```

默认前端 API 地址通过 `frontend/.env` 配置，参考 `frontend/.env.example`：

```powershell
VITE_API_BASE_URL=/
```

## AI 配置

JD 结构化解析、Resume 结构化解析、MatchResult 自动生成、Cover Letter 草稿生成和 Interview Prep 生成复用同一个 OpenAI-compatible chat completions 接口：

```powershell
LLM_BASE_URL=https://api.example.com/v1
LLM_API_KEY=your-api-key
LLM_MODEL_NAME=your-model-name
```

如果缺少这些配置，`POST /api/v1/jobs/{job_id}/parse`、`POST /api/v1/resumes/{resume_id}/parse`、`POST /api/v1/matches/analyze`、`POST /api/v1/artifacts/generate-cover-letter` 和 `POST /api/v1/artifacts/generate-interview-prep` 会返回清晰错误，不会伪造成功结果。自动化测试会 mock LLM 调用，不依赖真实外部模型。

`POST /api/v1/matches/analyze` 的前置条件是 resume 和 job 都已经完成结构化解析，也就是 `resumes.parsed_json` 和 `job_postings.parsed_json` 都有有效内容。本接口不会自动触发 JD parse 或 Resume parse。

`POST /api/v1/artifacts/generate-cover-letter` 的前置条件是 resume 和 job 都已完成 parse，且同一组 `resume_id + job_posting_id` 已经有 MatchResult。`language_mode` 支持 `zh`（仅中文）和 `bilingual`（先中文后英文），当前不支持纯英文模式。

`POST /api/v1/artifacts/generate-interview-prep` 的前置条件是 resume 和 job 都已完成 parse，且同一组 `resume_id + job_posting_id` 已经有 MatchResult。本接口只生成中文面试准备提纲。

## 最小接口示例

解析 JD：

```powershell
curl.exe -X POST http://localhost:8000/api/v1/jobs/1/parse
```

解析 Resume：

```powershell
curl.exe -X POST http://localhost:8000/api/v1/resumes/1/parse
```

自动生成 MatchResult：

```powershell
curl.exe -X POST http://localhost:8000/api/v1/matches/analyze `
  -H "Content-Type: application/json" `
  -d "{\"resume_id\":1,\"job_posting_id\":1}"
```

生成 Cover Letter 草稿：

```powershell
curl.exe -X POST http://localhost:8000/api/v1/artifacts/generate-cover-letter `
  -H "Content-Type: application/json" `
  -d "{\"resume_id\":1,\"job_posting_id\":1,\"language_mode\":\"zh\"}"
```

生成 Interview Prep：

```powershell
curl.exe -X POST http://localhost:8000/api/v1/artifacts/generate-interview-prep `
  -H "Content-Type: application/json" `
  -d "{\"resume_id\":1,\"job_posting_id\":1}"
```

记录 AI 产物反馈：

```powershell
curl.exe -X POST http://localhost:8000/api/v1/artifacts/1/feedback `
  -H "Content-Type: application/json" `
  -d "{\"feedback_type\":\"accepted\",\"note\":\"已采用为最终版本\"}"
```

查看 AI 产物反馈历史：

```powershell
curl.exe "http://localhost:8000/api/v1/artifacts/1/feedback?limit=20&offset=0"
```

当前 `feedback_type` 只支持 `accepted`、`edited_then_used`、`rejected`、`saved_for_later`，并且 feedback 仅针对 `GeneratedArtifact`。

创建 AI 产物：

```powershell
curl.exe -X POST http://localhost:8000/api/v1/artifacts `
  -H "Content-Type: application/json" `
  -d "{\"artifact_type\":\"cover_letter\",\"application_record_id\":1,\"title\":\"求职信草稿\",\"content_text\":\"Dear hiring team...\",\"content_json\":{\"sections\":[\"intro\",\"fit\"]},\"generator_type\":\"manual\"}"
```

查看 AI 产物详情：

```powershell
curl.exe http://localhost:8000/api/v1/artifacts/1
```

创建简历版本：

```powershell
curl.exe -X POST http://localhost:8000/api/v1/resume-versions `
  -H "Content-Type: application/json" `
  -d "{\"resume_id\":1,\"job_posting_id\":1,\"version_no\":1,\"version_label\":\"manual tailoring draft\",\"content\":\"# Tailored resume`nFastAPI workflow experience.\",\"change_summary\":\"突出 workflow 后端经验\"}"
```

查看某份简历的版本列表：

```powershell
curl.exe "http://localhost:8000/api/v1/resumes/1/versions?limit=20&offset=0"
```

执行投递阶段流转：

```powershell
curl.exe -X POST http://localhost:8000/api/v1/applications/1/transition `
  -H "Content-Type: application/json" `
  -d "{\"target_stage\":\"applied\",\"next_action\":\"三天后跟进 HR\",\"notes\":\"已投递定制版简历\",\"note\":\"从 saved 流转到 applied\",\"payload_json\":{\"source\":\"manual\"}}"
```

查看投递事件：

```powershell
curl.exe "http://localhost:8000/api/v1/applications/1/events?limit=20&offset=0"
```

## 停止本地服务

```powershell
docker compose down
```

停止容器并删除本地命名卷：

```powershell
docker compose down -v
```

## 连接信息

PostgreSQL:

- Host: `localhost`
- Port: `25432`
- User: `postgres`
- Password: `123456`
- Database: `jobpilot`
- URL: `postgresql://postgres:123456@localhost:25432/jobpilot`

Redis:

- Host: `localhost`
- Port: `26379`
- URL: `redis://localhost:26379/0`

## 验证 pgvector

PostgreSQL 启动后，可以验证 `vector` 扩展是否已安装：

```powershell
docker compose exec postgres psql -U postgres -d jobpilot -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"
```

如果看到一行 `vector` 记录，说明扩展已启用。
