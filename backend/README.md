# JobPilot Backend

JobPilot 后端是面向求职场景的 Agentic AI Workflow 系统的基础承载层。当前已经完成应用骨架、配置管理、PostgreSQL 异步访问、SQLAlchemy、Alembic、健康检查、Resume / JobPosting / MatchResult / ApplicationRecord 四个核心模块的最小 API 闭环、workflow 状态层、AI 产物承载层，以及 JD 结构化解析、Resume 结构化解析、MatchResult 自动生成、Cover Letter 草稿生成、Interview Prep 生成和 AI 产物反馈记录能力。

当前阶段可以理解为“Agent 化之前的业务能力底座”：核心求职 workflow 已经能跑通，下一阶段会在此基础上增加 Conversation / Message、Tool Adapter、LangChain StructuredTool、LangGraph 工作流、AgentRun / ToolCallLog、RAG 知识库和 Agent 质量评估。

第 24 步新增了两项后端优先整改：

- 最小用户作用域：通过 dev-only `X-User-Name` 请求头确定当前用户，把核心业务对象隔离到各自用户域下。
- recent-first / limit 规则显式化：核心 list 接口明确声明默认排序字段、recent-first 方向，以及 `limit + offset` 的轻量规则。

第 8 步新增了两类工作流能力：

- `ResumeVersion`：保存原始简历和面向岗位的定制版本。
- `ApplicationEvent`：记录投递阶段变化等工作流事件。

第 8.5 步新增了最小自动化测试底座，当前只覆盖关键 workflow 闭环，不代表完整测试体系。

第 9 步新增了 AI 产物承载层 `GeneratedArtifact`，用于保存手工写入或未来 AI 生成的求职材料产物；当前仍未接入真实 AI 生成。

第 10 步新增了第一个真实 AI 能力：JD 结构化解析。它通过一个很薄的 LLM 接入层解析 `job_postings.jd_text`，并把结构化结果写回 `job_postings.parsed_json`。

第 11 步新增了第二个真实 AI 能力：Resume 结构化解析。它复用同一个很薄的 LLM 接入层解析 `resumes.raw_text`，并把结构化结果写回 `resumes.parsed_json`，同时将 `resumes.parse_status` 更新为 `parsed`。

第 12 步新增了第三个真实 AI 能力：基于结构化 Resume + 结构化 JD 自动生成 MatchResult。它读取 `resumes.parsed_json` 和 `job_postings.parsed_json`，调用同一个 LLM 接入层生成结构化匹配分析，并新增一条 `match_results` 记录。

第 13 步新增了第一类生成能力：Cover Letter 草稿生成。它读取结构化 Resume、结构化 JD 和最近一条 MatchResult，调用同一个 LLM 接入层生成求职信草稿，并新增一条 `generated_artifacts` 记录。

第 14 步新增了第二类生成能力：Interview Prep 生成。它读取结构化 Resume、结构化 JD 和最近一条 MatchResult，调用同一个 LLM 接入层生成中文面试准备提纲，并新增一条 `generated_artifacts` 记录。

第 15 步新增了最小 feedback 闭环：记录用户对 `GeneratedArtifact` 的采纳、编辑后采用、拒绝或稍后保存反馈。当前 feedback 只是事件记录层，不代表完整评测系统，也不会自动修改 artifact 状态或触发重新生成。

当前仍不包含真实 AI 对话、RAG、LangChain、LangGraph、认证登录、文件上传、Redis 业务逻辑、自动提醒、运行日志或复杂状态机。

## 下一阶段 Agent 后端方向

后端下一阶段会把 AI 助手从“产品壳”升级为可调用、可追踪、可校验的 Agent Runtime。目标流程：

```text
POST /api/v1/assistant/run
↓
写入 user message，创建 AgentRun
↓
读取业务上下文、历史 messages 和 memory_summary
↓
构造 system prompt、任务规则、工具规则和输出格式说明
↓
进入 LangGraph workflow
↓
intent 路由到受控节点
↓
LangChain StructuredTool 校验参数格式
↓
Tool Adapter 校验用户作用域、业务前置条件和写入权限
↓
调用已有 service / LLM client / RAG retriever
↓
写入 ToolCallLog
↓
生成最终回复或结构化产物，做最终 Schema 校验和 repair
↓
写入 assistant message / generated_artifacts
↓
更新 memory_summary 和 AgentRun 状态
```

后端分层目标：

```text
api/
  assistant.py                 # planned: /assistant/run
agent/
  state.py                     # planned: LangGraph state
  graph.py                     # planned: workflow construction
  nodes.py                     # planned: intent / tool / response nodes
  prompts.py                   # planned: system prompt and repair prompt
  tools.py                     # planned: LangChain StructuredTool registry
  tool_adapters.py             # planned: business validation + service calls
services/
  existing services            # keep real business logic here
llm/
  client.py                    # keep OpenAI-compatible model adapter
```

LangGraph 不替代现有 LLM client；它只负责编排。LangChain Tool 不承载复杂业务逻辑；它只作为参数 schema 和工具调用入口，真实校验和执行放在 Tool Adapter 与已有 service 中。

## 最小用户作用域

当前没有完整注册登录系统，但后端已经引入最小用户域模型和请求作用域：

- 当前用户通过 dev-only 请求头 `X-User-Name` 解析
- 未显式传 header 时，默认落到 `demo`
- 当前仓库内置了 `demo`、`sandbox`、`test` 三类最小用户
- `test` 主要用于 pytest 数据隔离，不建议作为正常演示用户暴露到前端

当前用户解析集中在 `app/api/deps.py` 的 `get_current_user()`，底层用户创建和作用域 helper 位于 `app/services/user_scope_service.py`。当前不会做 JWT、refresh token、登录页或注册页。

## 环境要求

- 使用 `uv` 管理 Python 环境和依赖
- 使用仓库根目录的 `compose.yaml` 启动本地 PostgreSQL 和 Redis

## 安装依赖

在仓库根目录执行：

```powershell
uv --cache-dir .uv-cache --directory backend sync
```

依赖由 `pyproject.toml` 和 `uv.lock` 管理，不使用 `requirements.txt` 作为主要依赖来源。

## 启动 FastAPI

```powershell
uv --cache-dir .uv-cache --directory backend run uvicorn app.main:app --reload
```

启动后可以访问：

- `GET http://localhost:8000/health`
- `GET http://localhost:8000/health/db`
- `POST http://localhost:8000/api/v1/resumes`
- `GET http://localhost:8000/api/v1/resumes`
- `GET http://localhost:8000/api/v1/resumes/{resume_id}`
- `PATCH http://localhost:8000/api/v1/resumes/{resume_id}`
- `POST http://localhost:8000/api/v1/resumes/{resume_id}/parse`
- `POST http://localhost:8000/api/v1/jobs`
- `GET http://localhost:8000/api/v1/jobs`
- `GET http://localhost:8000/api/v1/jobs/{job_id}`
- `PATCH http://localhost:8000/api/v1/jobs/{job_id}`
- `POST http://localhost:8000/api/v1/jobs/{job_id}/parse`
- `POST http://localhost:8000/api/v1/matches`
- `POST http://localhost:8000/api/v1/matches/analyze`
- `GET http://localhost:8000/api/v1/matches`
- `GET http://localhost:8000/api/v1/matches/{match_id}`
- `PATCH http://localhost:8000/api/v1/matches/{match_id}`
- `POST http://localhost:8000/api/v1/applications`
- `GET http://localhost:8000/api/v1/applications`
- `GET http://localhost:8000/api/v1/applications/{application_id}`
- `PATCH http://localhost:8000/api/v1/applications/{application_id}`
- `POST http://localhost:8000/api/v1/resume-versions`
- `GET http://localhost:8000/api/v1/resume-versions`
- `GET http://localhost:8000/api/v1/resume-versions/{version_id}`
- `PATCH http://localhost:8000/api/v1/resume-versions/{version_id}`
- `GET http://localhost:8000/api/v1/resumes/{resume_id}/versions`
- `GET http://localhost:8000/api/v1/applications/{application_id}/events`
- `POST http://localhost:8000/api/v1/applications/{application_id}/transition`
- `POST http://localhost:8000/api/v1/artifacts`
- `POST http://localhost:8000/api/v1/artifacts/generate-cover-letter`
- `POST http://localhost:8000/api/v1/artifacts/generate-interview-prep`
- `POST http://localhost:8000/api/v1/artifacts/{artifact_id}/feedback`
- `GET http://localhost:8000/api/v1/artifacts/{artifact_id}/feedback`
- `GET http://localhost:8000/api/v1/artifacts`
- `GET http://localhost:8000/api/v1/artifacts/{artifact_id}`
- `PATCH http://localhost:8000/api/v1/artifacts/{artifact_id}`

## 执行 Alembic 迁移

模型变化后生成迁移：

```powershell
uv --cache-dir .uv-cache --directory backend run alembic revision --autogenerate -m "create generated artifacts table"
```

执行迁移：

```powershell
uv --cache-dir .uv-cache --directory backend run alembic upgrade head
```

查看当前迁移版本：

```powershell
uv --cache-dir .uv-cache --directory backend run alembic current
```

## 运行测试

当前测试使用 `pytest` 和 FastAPI `TestClient` 发起接口请求：

```powershell
uv --cache-dir .uv-cache --directory backend run pytest
```

测试会连接当前后端配置中的 PostgreSQL 数据库。由于当前项目还没有独立测试数据库配置，测试通过 API 创建带 `pytest-jobpilot-*` 唯一标记的前置数据，不依赖已有人工数据或固定 id。当前测试不会覆盖完整系统，只覆盖关键 workflow、AI 产物承载闭环、JD 解析闭环、Resume 解析闭环、MatchResult 自动生成闭环、Cover Letter 草稿生成闭环、Interview Prep 生成闭环和 artifact feedback 闭环。JD / Resume 解析、MatchResult 自动生成、Cover Letter 草稿生成和 Interview Prep 生成测试使用 monkeypatch 替代真实 LLM 调用。

pytest 的 `TestClient` 现在默认附带 `X-User-Name: test`，因此测试数据默认写入 `test` 用户作用域，不会污染 `demo` / `sandbox` 演示数据。

## AI 配置

JD 结构化解析、Resume 结构化解析、MatchResult 自动生成、Cover Letter 草稿生成和 Interview Prep 生成复用同一个 OpenAI-compatible chat completions 接口：

```powershell
LLM_BASE_URL=https://api.example.com/v1
LLM_API_KEY=your-api-key
LLM_MODEL_NAME=your-model-name
```

`LLM_BASE_URL` 会拼接 `/chat/completions` 发起请求。缺少配置时，parse / analyze / generate 接口会返回清晰错误，不会伪造成功结果。自动化测试会 mock LLM 调用，不依赖真实外部模型。

下一阶段接入 LangGraph 后，仍会保留 `app/llm/client.py` 作为模型适配层，避免业务代码直接依赖某个模型供应商或框架实现。

## 当前核心表

- `users`：最小用户域表，负责数据归属和测试数据隔离，不承接完整认证能力。
- `resumes`：保存简历文本、来源、解析状态、结构化解析结果和内容哈希。
- `job_postings`：保存公司、岗位、城市、JD 原文、来源链接、解析结果和岗位状态。
- `match_results`：保存某份简历和某个岗位之间的匹配分数、优势、劣势、缺失关键词和建议。
- `application_records`：保存某份简历对某个岗位的投递/跟进状态、渠道、下一步动作和备注。
- `resume_versions`：保存简历版本、关联岗位、版本内容、来源类型和变更摘要。
- `application_events`：保存投递记录的阶段变化事件、操作来源、附加 payload 和备注。
- `generated_artifacts`：保存求职信、简历摘要、面试准备提纲等 AI 产物承载记录，目前支持手工写入、更新、Cover Letter 草稿生成和 Interview Prep 生成写入。
- `artifact_feedback_events`：保存用户对 AI 产物的采纳、编辑后采用、拒绝或稍后保存反馈事件。

第 24 步后，`resumes`、`job_postings`、`match_results`、`generated_artifacts`、`application_records` 都有非空 `user_id`。历史记录在 migration 中统一回填到 `demo` 用户，避免遗留 NULL 归属破坏主链路。`resume_versions`、`application_events`、`artifact_feedback_events` 则继续通过父对象间接归属。

下一阶段计划新增的核心表：

- `conversations`：保存 AI 助手对话入口、标题、当前用户、上下文摘要和 `memory_summary`。
- `messages`：保存用户消息、助手回复、上下文引用、状态、错误信息和元数据。
- `agent_runs`：保存一次 Agent 执行的状态、intent、开始/结束时间、错误信息和触发消息。
- `tool_call_logs`：保存工具调用名称、输入、输出、耗时、状态和错误信息。
- `knowledge_bases`：保存知识库分组，如公司资料、项目素材、面试准备资料。
- `knowledge_documents`：保存用户录入或上传的资料原文和元信息。
- `knowledge_chunks`：保存切块文本、embedding 向量和检索元数据。
- `agent_feedback_events`：保存用户对 Agent 回复或运行结果的质量反馈。

## 当前完成度口径

| 模块 | 完成度估算 |
| --- | ---: |
| 后端应用骨架 / DB / migration | 85% |
| 核心求职 workflow API | 70%-75% |
| 结构化解析与材料生成 | 60%-65% |
| 测试覆盖 | 45%-50% |
| AI Agent Runtime | 0%-10% |
| RAG 知识库 | 0%-10% |
| 运行日志与评估 | 0%-10% |

## GeneratedArtifact API

当前 GeneratedArtifact 模块支持最小闭环：

- 创建产物：`POST /api/v1/artifacts`
- 生成 Cover Letter 草稿：`POST /api/v1/artifacts/generate-cover-letter`
- 生成 Interview Prep：`POST /api/v1/artifacts/generate-interview-prep`
- 创建产物反馈：`POST /api/v1/artifacts/{artifact_id}/feedback`
- 查看产物反馈：`GET /api/v1/artifacts/{artifact_id}/feedback`
- 产物列表：`GET /api/v1/artifacts?limit=20&offset=0`
- 产物详情：`GET /api/v1/artifacts/{artifact_id}`
- 更新产物：`PATCH /api/v1/artifacts/{artifact_id}`

创建或更新时，`resume_id`、`job_posting_id`、`application_record_id` 至少要有一个非空；如果传入这些关联 id，会校验对应业务对象是否存在。当前不做模板渲染、PDF/DOCX 导出、删除、复杂搜索、复杂过滤或复杂排序。

当前 feedback 仅针对 `GeneratedArtifact`，只是最小事件记录层，不做评测聚合、不自动修改 `GeneratedArtifact.status`，也不触发重新生成。

### 调用示例

创建产物：

```powershell
curl.exe -X POST http://localhost:8000/api/v1/artifacts `
  -H "Content-Type: application/json" `
  -d "{\"artifact_type\":\"cover_letter\",\"application_record_id\":1,\"title\":\"求职信草稿\",\"content_text\":\"Dear hiring team...\",\"content_json\":{\"sections\":[\"intro\",\"fit\"]},\"status\":\"draft\",\"generator_type\":\"manual\"}"
```

查看列表：

```powershell
curl.exe "http://localhost:8000/api/v1/artifacts?limit=20&offset=0"
```

查看详情：

```powershell
curl.exe http://localhost:8000/api/v1/artifacts/1
```

更新产物：

```powershell
curl.exe -X PATCH http://localhost:8000/api/v1/artifacts/1 `
  -H "Content-Type: application/json" `
  -d "{\"status\":\"ready\",\"content_text\":\"Updated manual draft.\"}"
```

## ArtifactFeedback API

当前 ArtifactFeedback 模块支持最小闭环：

- 创建反馈事件：`POST /api/v1/artifacts/{artifact_id}/feedback`
- 查看某个产物的反馈历史：`GET /api/v1/artifacts/{artifact_id}/feedback?limit=20&offset=0`

`feedback_type` 当前只允许：

- `accepted`
- `edited_then_used`
- `rejected`
- `saved_for_later`

### 调用示例

```powershell
curl.exe -X POST http://localhost:8000/api/v1/artifacts/1/feedback `
  -H "Content-Type: application/json" `
  -d "{\"feedback_type\":\"accepted\",\"note\":\"已采用为最终版本\"}"
```

```powershell
curl.exe "http://localhost:8000/api/v1/artifacts/1/feedback?limit=20&offset=0"
```

## CoverLetterGeneration API

当前 Cover Letter 草稿生成接口支持最小闭环：

- 生成单份求职信草稿：`POST /api/v1/artifacts/generate-cover-letter`

接口会读取 `resumes.parsed_json`、`job_postings.parsed_json` 和最近一条同组 `match_results`，调用 LLM 生成求职信正文，并新增一条 `generated_artifacts` 记录。生成结果会写入 `content_text`，最小元数据会写入 `content_json`，包括 `artifact_type`、`language_mode`、`based_on_match_result_id` 和 `key_points`。

前置条件：

- Resume 和 JobPosting 都需要先完成 parse。
- 同一组 `resume_id + job_posting_id` 需要先完成 MatchResult 自动生成或已有 match result。
- 如果传入 `application_record_id`，它必须存在并且与请求中的 resume/job 一致。

`language_mode` 当前仅支持：

- `zh`：仅生成中文求职信。
- `bilingual`：先生成中文，再生成英文。

当前不支持纯英文模式，不做批量生成、异步队列、流式返回、模板系统、PDF/DOCX 导出或写入 `resume_versions`。

### 调用示例

```powershell
curl.exe -X POST http://localhost:8000/api/v1/artifacts/generate-cover-letter `
  -H "Content-Type: application/json" `
  -d "{\"resume_id\":1,\"job_posting_id\":1,\"language_mode\":\"zh\"}"
```

成功后接口仍返回 `GeneratedArtifactRead` 风格的产物详情。

## InterviewPrepGeneration API

当前 Interview Prep 生成接口支持最小闭环：

- 生成单份中文面试准备提纲：`POST /api/v1/artifacts/generate-interview-prep`

接口会读取 `resumes.parsed_json`、`job_postings.parsed_json` 和最近一条同组 `match_results`，调用 LLM 生成中文面试准备提纲，并新增一条 `generated_artifacts` 记录。生成结果会写入 `content_text`，最小元数据会写入 `content_json`，包括 `artifact_type`、`based_on_match_result_id`、`focus_topics` 和 `question_count`。

前置条件：

- Resume 和 JobPosting 都需要先完成 parse。
- 同一组 `resume_id + job_posting_id` 需要先完成 MatchResult 自动生成或已有 match result。
- 如果传入 `application_record_id`，它必须存在并且与请求中的 resume/job 一致。

当前只生成中文 Interview Prep，不做双语模式、批量生成、异步队列、流式返回、模板系统、PDF/DOCX 导出或写入 `resume_versions`。

### 调用示例

```powershell
curl.exe -X POST http://localhost:8000/api/v1/artifacts/generate-interview-prep `
  -H "Content-Type: application/json" `
  -d "{\"resume_id\":1,\"job_posting_id\":1}"
```

成功后接口仍返回 `GeneratedArtifactRead` 风格的产物详情。

## JobParsing API

当前 JD 解析接口支持最小闭环：

- 解析单个岗位：`POST /api/v1/jobs/{job_id}/parse`

接口会读取 `job_postings.jd_text`，调用 LLM，要求模型返回结构化 JSON，并将结果写入 `job_postings.parsed_json`。当前不做批量解析、异步队列、流式返回、RAG 或复杂 prompt 管理。

### 调用示例

```powershell
curl.exe -X POST http://localhost:8000/api/v1/jobs/1/parse
```

成功后接口仍返回 `JobPostingRead` 风格的岗位详情，解析结果位于 `parsed_json`。

## ResumeParsing API

当前 Resume 解析接口支持最小闭环：

- 解析单份简历：`POST /api/v1/resumes/{resume_id}/parse`

接口会读取 `resumes.raw_text`，调用 LLM，要求模型返回结构化 JSON，并将结果写入 `resumes.parsed_json`。解析成功后，`resumes.parse_status` 会更新为 `parsed`。当前不做文件上传、批量解析、异步队列、流式返回、RAG 或复杂 prompt 管理。

### 调用示例

```powershell
curl.exe -X POST http://localhost:8000/api/v1/resumes/1/parse
```

成功后接口仍返回 `ResumeRead` 风格的简历详情，解析结果位于 `parsed_json`。

## MatchAnalysis API

当前 MatchResult 自动生成接口支持最小闭环：

- 分析单组简历和岗位：`POST /api/v1/matches/analyze`

接口会读取 `resumes.parsed_json` 和 `job_postings.parsed_json`，调用 LLM，要求模型返回结构化 JSON，并新增一条 `match_results` 记录。前置条件是 Resume 和 JobPosting 都已经完成结构化解析；如果任意一侧缺少 `parsed_json`，接口会返回 400，不会自动触发 JD parse 或 Resume parse。当前不做去重、覆盖旧结果、批量分析、异步队列、流式返回、RAG 或复杂 prompt 管理。

### 调用示例

```powershell
curl.exe -X POST http://localhost:8000/api/v1/matches/analyze `
  -H "Content-Type: application/json" `
  -d "{\"resume_id\":1,\"job_posting_id\":1}"
```

成功后接口仍返回 `MatchResultRead` 风格的匹配详情。

## ResumeVersion API

当前 ResumeVersion 模块支持最小闭环：

- 创建简历版本：`POST /api/v1/resume-versions`
- 简历版本列表：`GET /api/v1/resume-versions?limit=20&offset=0`
- 简历版本详情：`GET /api/v1/resume-versions/{version_id}`
- 更新简历版本：`PATCH /api/v1/resume-versions/{version_id}`
- 查看某份简历的版本：`GET /api/v1/resumes/{resume_id}/versions?limit=20&offset=0`

创建时会校验 `resume_id` 是否存在；如果传入 `job_posting_id`，也会校验岗位是否存在。当前不做版本号自动递增、唯一约束或复杂版本切换。

### 调用示例

创建简历版本：

```powershell
curl.exe -X POST http://localhost:8000/api/v1/resume-versions `
  -H "Content-Type: application/json" `
  -d "{\"resume_id\":1,\"job_posting_id\":1,\"version_no\":1,\"version_label\":\"manual tailoring draft\",\"content\":\"# Tailored resume`nFastAPI workflow experience.\",\"content_format\":\"markdown\",\"source_type\":\"manual\",\"change_summary\":\"突出 workflow 后端经验\",\"is_active\":true}"
```

查看版本列表：

```powershell
curl.exe "http://localhost:8000/api/v1/resume-versions?limit=20&offset=0"
```

查看某份简历的版本：

```powershell
curl.exe "http://localhost:8000/api/v1/resumes/1/versions?limit=20&offset=0"
```

更新简历版本：

```powershell
curl.exe -X PATCH http://localhost:8000/api/v1/resume-versions/1 `
  -H "Content-Type: application/json" `
  -d "{\"version_label\":\"manual tailoring draft v2\",\"change_summary\":\"补充项目经历\"}"
```

## ApplicationEvent 与 Transition API

当前不暴露手工创建 ApplicationEvent 的 CRUD 接口。事件由投递阶段流转动作内部创建。

- 查看投递事件：`GET /api/v1/applications/{application_id}/events?limit=20&offset=0`
- 执行阶段流转：`POST /api/v1/applications/{application_id}/transition`

`transition` 会读取投递记录，记录旧的 `current_stage`，用 `target_stage` 更新投递记录，并创建一条 `event_type = "stage_changed"` 的 `application_events` 记录。它还可以同时更新 `next_action`、`next_action_at` 和 `notes`。

### 调用示例

执行阶段流转：

```powershell
curl.exe -X POST http://localhost:8000/api/v1/applications/1/transition `
  -H "Content-Type: application/json" `
  -d "{\"target_stage\":\"applied\",\"next_action\":\"三天后跟进 HR\",\"next_action_at\":\"2026-04-25T10:00:00+08:00\",\"notes\":\"已投递定制版简历\",\"note\":\"从 saved 流转到 applied\",\"payload_json\":{\"source\":\"manual\"}}"
```

查看投递事件：

```powershell
curl.exe "http://localhost:8000/api/v1/applications/1/events?limit=20&offset=0"
```

## 已有核心 API

已有 Resume / JobPosting / MatchResult / ApplicationRecord 模块仍保持第 7 步的最小闭环：创建、列表、详情、更新。创建 MatchResult 和 ApplicationRecord 时会校验 `resume_id` 与 `job_posting_id` 是否存在。

第 24 步后，核心 list 接口的 recent-first 规则显式如下：

- `GET /api/v1/jobs`：`updated_at DESC, id DESC`
- `GET /api/v1/resumes`：`updated_at DESC, id DESC`
- `GET /api/v1/applications`：`updated_at DESC, id DESC`
- `GET /api/v1/matches`：`created_at DESC, id DESC`
- `GET /api/v1/artifacts`：`created_at DESC, id DESC`

这些 list 接口统一支持：

- `limit`：默认 20，最大 100
- `offset`：默认 0

Dashboard 和工作页当前都应把它们当作“当前用户作用域下的 recent-first 轻量窗口”，而不是隐式全量列表或总量统计。

## 本阶段完成

- 新增 `ResumeVersion`、`ApplicationEvent` 两个 SQLAlchemy 模型。
- 新增 ResumeVersion 的创建、列表、详情、更新、按简历查看版本接口。
- 新增 ApplicationEvent 的事件列表 schema 和接口。
- 新增 ApplicationTransitionRequest，并通过 transition 动作创建事件。
- 新增 `backend/app/services/application_transition_service.py`，承载投递阶段流转的最小业务逻辑。
- 生成并执行 Alembic 迁移，创建 `resume_versions` 和 `application_events`。
- 保留已有四个核心模块的文件结构、命名风格、响应风格和接口行为。
- 新增最小自动化测试底座，覆盖 ResumeVersion 创建/列表、Application transition、ApplicationEvent 查询和 404 失败用例。
- 新增 `GeneratedArtifact` SQLAlchemy 模型、schemas 和 `/api/v1/artifacts` 最小 API 闭环。
- 新增 GeneratedArtifact 最小自动化测试，覆盖创建成功、必须关联业务对象和详情查询。
- 补齐 `GET /api/v1/applications/{application_id}/events` 返回中的 `payload_json` 和 `note` 字段。
- 新增最小 LLM client、JD 解析 schema、JD parse service 和 `POST /api/v1/jobs/{job_id}/parse`。
- 新增 JD 解析测试，覆盖 parse 成功、岗位不存在、空 JD、LLM 非 JSON 错误。
- 新增 Resume 解析 schema、Resume parse service 和 `POST /api/v1/resumes/{resume_id}/parse`。
- Resume parse 复用现有 LLM client，并复用 JD parse 已有的 Markdown JSON code fence 清洗行为。
- 新增 Resume 解析测试，覆盖 parse 成功、简历不存在、空简历、LLM 非 JSON、schema 非法和 fenced JSON。
- 新增 Match 分析 schema、Match analyze service 和 `POST /api/v1/matches/analyze`。
- Match analyze 复用现有 LLM client，并复用已有 Markdown JSON code fence 清洗行为。
- 新增 Match 分析测试，覆盖分析成功、简历不存在、岗位不存在、Resume 未解析、Job 未解析、LLM 非 JSON、schema 非法、配置错误和 fenced JSON。
- 新增 Cover Letter 生成 schema、Cover Letter service 和 `POST /api/v1/artifacts/generate-cover-letter`。
- Cover Letter 生成复用现有 LLM client，结果写入 `GeneratedArtifact`，不新增数据库表。
- 新增 Cover Letter 生成测试，覆盖中文成功、双语成功、对象不存在、application_record 不匹配、前置解析缺失、缺 match result、非法 language_mode、LLM 配置/调用失败、空结果和纯英文无效结果。
- 新增 Interview Prep 生成 schema、Interview Prep service 和 `POST /api/v1/artifacts/generate-interview-prep`。
- Interview Prep 生成复用现有 LLM client，结果写入 `GeneratedArtifact`，不新增数据库表。
- 新增 Interview Prep 生成测试，覆盖成功、对象不存在、application_record 不匹配、前置解析缺失、缺 match result、LLM 配置/调用失败、空结果、纯英文无效结果和空泛中文无效结果。
- 新增 `ArtifactFeedbackEvent` SQLAlchemy 模型、schemas、service 和 `POST/GET /api/v1/artifacts/{artifact_id}/feedback`。
- 生成并执行 Alembic 迁移，创建 `artifact_feedback_events` 表。
- 新增 artifact feedback 测试，覆盖创建成功、列表倒序、artifact 不存在和非法 feedback_type。

## 本阶段故意没做

- 没有接入除 Cover Letter 草稿和 Interview Prep 外的其他真实 AI 生成逻辑。
- 没有做模板渲染、PDF/DOCX 导出或产物删除接口。
- 没有引入 LangChain、LangGraph 或 RAG。
- 没有 Conversation / Message、Tool Adapter、AgentRun、ToolCallLog 或 Agent Eval。
- 没有做简历改写/定制生成、多种 artifact 一起生成或完整面试题库系统。
- 没有做完整评测系统、feedback 聚合分数、统计报表、dashboard、自动重生成或训练数据导出。
- 没有让 feedback 自动修改 `GeneratedArtifact.status` 或写回 `content_json`。
- 没有做批量解析、异步队列、流式输出或复杂 prompt 管理系统。
- 没有增加认证登录、前端、文件上传、Redis 业务逻辑或自动提醒。
- 没有补 delete、复杂搜索、复杂过滤、复杂排序或复杂状态机。
- 没有把已有四个核心模块重构成 service 层。
- 没有引入 CI/CD 或完整测试体系。

## 目录结构

```text
backend/
├── alembic/
│   ├── versions/
│   │   ├── 5d21bc9bb45b_create_workflow_layer_tables.py
│   │   ├── 481b01b23f23_create_generated_artifacts_table.py
│   │   ├── 63fb9442ddd4_create_core_business_tables.py
│   │   ├── 768a3418a62d_create_users_table.py
│   │   └── f938bb597dcc_create_artifact_feedback_events_table.py
│   ├── env.py
│   ├── README
│   └── script.py.mako
├── app/
│   ├── api/
│   │   ├── application_events.py
│   │   ├── applications.py
│   │   ├── artifacts.py
│   │   ├── health.py
│   │   ├── jobs.py
│   │   ├── matches.py
│   │   ├── resume_versions.py
│   │   └── resumes.py
│   ├── core/
│   │   └── config.py
│   ├── db/
│   │   ├── base.py
│   │   └── session.py
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── client.py
│   │   └── json_utils.py
│   ├── models/
│   │   ├── application_event.py
│   │   ├── application_record.py
│   │   ├── artifact_feedback_event.py
│   │   ├── generated_artifact.py
│   │   ├── job_posting.py
│   │   ├── match_result.py
│   │   ├── resume.py
│   │   ├── resume_version.py
│   │   └── user.py
│   ├── schemas/
│   │   ├── application_event.py
│   │   ├── application_record.py
│   │   ├── artifact_feedback.py
│   │   ├── cover_letter_generation.py
│   │   ├── generated_artifact.py
│   │   ├── interview_prep_generation.py
│   │   ├── job_parsing.py
│   │   ├── job_posting.py
│   │   ├── match_analysis.py
│   │   ├── match_result.py
│   │   ├── resume_parsing.py
│   │   ├── resume.py
│   │   └── resume_version.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── application_transition_service.py
│   │   ├── artifact_feedback_service.py
│   │   ├── cover_letter_service.py
│   │   ├── interview_prep_service.py
│   │   ├── job_parsing_service.py
│   │   ├── match_analysis_service.py
│   │   └── resume_parsing_service.py
│   └── main.py
├── tests/
│   ├── conftest.py
│   ├── test_application_transition.py
│   ├── test_artifact_feedback.py
│   ├── test_cover_letter_generation.py
│   ├── test_generated_artifacts.py
│   ├── test_interview_prep_generation.py
│   ├── test_job_parsing.py
│   ├── test_match_analysis.py
│   ├── test_resume_parsing.py
│   └── test_resume_versions.py
├── .env.example
├── alembic.ini
├── pyproject.toml
├── README.md
└── uv.lock
```
