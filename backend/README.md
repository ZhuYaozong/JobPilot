# JobPilot Backend

`backend/` 是 JobPilot 的后端服务，负责业务 API、数据库模型、LLM 生成服务、LangGraph Agent Runtime、RAG 知识库和工具调用审计。它不是一个只暴露 CRUD 的后台，而是围绕求职流程构建的可追踪 AI workflow 层。

当前后端已经完成：

- 岗位、简历、匹配、材料、投递的核心业务 API。
- JD / Resume 结构化解析、匹配分析、求职信、面试准备和定制简历生成。
- AI 草稿端点：JD 文本 / URL → LLM 起草岗位；简历文本 → LLM 起草简历；不落库,前端预览编辑后再保存。
- 通用导出端点：简历版本与求职材料导出 Markdown / DOCX。
- JWT 注册 / 登录 / me，bcrypt 密码哈希；与 dev 模式 `X-User-Name` 并存。
- Conversation / Message / AgentRun / ToolCallLog 的 Agent 数据层。
- LangGraph 1.x 工作流和基于 `langchain-core` 的工具抽象。
- 20 个 Agent 工具：list / read / parse / draft / create / update / 投递 / 知识库写入 / 已生成材料查询 / 检索 / 匹配 / 求职信 / 面试准备 / 定制简历。
- Agent 可观测端点：列出会话所有 AgentRun + 嵌套 ToolCallLog(arguments / result / error_detail / latency),供前端展开看完整工具调用详情。
- write 类工具必填字段缺失统一走 `missing_required_field` 业务错,引导 LLM 自然追问而不是抛 ValidationError。
- SSE 流式 Assistant。
- KnowledgeBase / KnowledgeDocument / KnowledgeChunk 数据层。
- 自研文本切片、OpenAI-compatible embedding client、pgvector 检索。
- 用户作用域隔离(JWT 用户与 dev 用户共享同一份作用域规则)。

## Technology

- Python 3.12+
- FastAPI
- SQLAlchemy async
- Alembic
- PostgreSQL + pgvector
- Redis
- LangGraph 1.x
- LangChain-core 1.x
- httpx
- uv

项目约束：

- 不引入 `langchain-openai`
- 不引入 `langchain-community`
- 不引入 `langchain-text-splitters`
- Chat 和 embedding 调用统一走自研 OpenAI-compatible client

## Architecture

```text
backend/
├── app/
│   ├── api/          # HTTP routes and dependency wiring
│   ├── agent/        # LangGraph workflow, prompts, tool registry, adapters
│   ├── core/         # Settings
│   ├── db/           # Async database session
│   ├── llm/          # OpenAI-compatible chat and embedding clients
│   ├── models/       # SQLAlchemy models
│   ├── schemas/      # Pydantic request/response schemas
│   └── services/     # Business logic, parsing, generation, indexing
├── alembic/          # Database migrations
└── tests/            # pytest suite
```

分层约定：

- `api/` 不承载复杂业务逻辑，只做 HTTP 入参、依赖注入、错误边界和响应模型。
- `services/` 是业务逻辑中心，负责用户作用域、前置条件、数据库写入和 LLM 生成。
- `agent/tools/` 包装业务 service，给 Agent 提供稳定工具入口。
- `agent/tool_adapter.py` 负责工具调用日志、参数校验、业务错误分类和用户作用域。
- `agent/workflow.py` 负责编排 ReAct 风格多工具流程，不直接写业务规则。
- `llm/` 是模型供应商适配层，业务模块不直接依赖具体云厂商 SDK。

## Configuration

复制配置文件：

```powershell
Copy-Item ../.env.example ../.env
Copy-Item .env.example .env
```

基础配置：

```env
APP_NAME=JobPilot Backend
APP_ENV=local
APP_DEBUG=true

DATABASE_URL=postgresql+asyncpg://postgres:123456@127.0.0.1:25432/jobpilot
REDIS_URL=redis://127.0.0.1:26379/0
```

LLM 配置：

```env
LLM_BASE_URL=https://api.example.com/v1
LLM_API_KEY=your-api-key
LLM_MODEL_NAME=your-chat-model
```

Embedding 配置：

```env
EMBEDDING_BASE_URL=https://api.example.com/v1
EMBEDDING_API_KEY=your-api-key
EMBEDDING_MODEL_NAME=your-embedding-model
EMBEDDING_DIMENSIONS=1536
```

`EMBEDDING_*` 可以独立于 `LLM_*`。如果不设置 embedding endpoint，`EmbeddingClient` 会尝试复用 LLM endpoint；如果仍缺少必要配置，知识库索引会失败并把错误写入文档状态，用户可修正配置后重新索引。

认证与生产安全配置：

```env
AUTH_SECRET_KEY=change-this-to-a-long-random-secret
AUTH_ALGORITHM=HS256
AUTH_ACCESS_TOKEN_EXPIRE_MINUTES=1440
AUTH_DEV_MODE=true
```

`AUTH_DEV_MODE=true` 会允许 `X-User-Name` header 自动创建/切换本地用户，只应在本地开发和测试中使用。生产部署请设置 `APP_ENV=production`、`APP_DEBUG=false`、`AUTH_DEV_MODE=false`，并使用足够长的随机 `AUTH_SECRET_KEY`。

## Local Development

在仓库根目录启动依赖：

```powershell
docker compose up -d
```

安装依赖：

```powershell
uv --cache-dir .uv-cache --directory backend sync
```

执行迁移：

```powershell
uv --cache-dir .uv-cache --directory backend run alembic upgrade head
```

启动服务：

```powershell
uv --cache-dir .uv-cache --directory backend run uvicorn app.main:app --reload
```

健康检查：

```text
GET http://localhost:8000/health
GET http://localhost:8000/health/db
```

## Testing

运行全部后端测试：

```powershell
uv --cache-dir .uv-cache --directory backend run pytest
```

运行指定测试文件：

```powershell
uv --cache-dir .uv-cache --directory backend run pytest tests/test_assistant_stream.py
```

测试说明：

- pytest 使用真实 FastAPI 路由和测试客户端。
- 默认测试用户为 `X-User-Name: test`，避免污染 `demo` / `sandbox` 演示数据。
- LLM、embedding 和 URL 抓取相关测试使用 monkeypatch / mock，不依赖真实外部服务。
- 测试数据库仍指向当前配置的 PostgreSQL，运行前需确保本地 compose 服务可用并已执行迁移。

## Agent Eval

`app/eval/` 是一个独立的 agent 行为回归框架（切片 8'a），跟 pytest 是分开的两套：

- pytest 验证"代码是否正确"。
- eval 验证"agent 在场景里是否做对了事"——选对了工具、调用顺序合理、最终回复包含关键事实。

跑全部 baseline case（默认走 fake LLM + fake embedding，不消耗 token）：

```powershell
uv --cache-dir .uv-cache --directory backend run python -m app.eval.cli
```

常用选项：

- `--filter NAME`：正则匹配 case 名，只跑命中的（如 `--filter search`）。
- `--live`：用真 `LLMClient` + `EmbeddingClient`，需要 `LLM_*` / `EMBEDDING_*` 环境变量已配置。
- `--report-dir PATH`：自定义报告输出根目录（默认 `./eval-reports/`，每次跑会生成时间戳子目录）。

每次跑会输出：

- 控制台逐行 `[OK] / [FAIL]` 标记 + 失败原因摘要。
- `eval-reports/<timestamp>/summary.md`：汇总表 + 失败明细。
- `eval-reports/<timestamp>/case-<name>.json`：每 case 的完整 trace（工具调用、参数、结果、最终回复）。

新增 case 时只需在 `app/eval/datasets/` 下加 yaml，runner 会自动加载；参考 `v1.yaml` 的 fake_responses 关键词分发约定。框架本身的回归测试在 `tests/test_eval_runner.py`，跟 pytest 一起跑。

## User Scope

后端支持两条认证路径,二者**共享同一份用户作用域规则**:

### JWT 认证(主路径)

- `POST /api/auth/register`:用户名 + email(可选) + 密码注册,bcrypt 哈希。
- `POST /api/auth/login`:用户名 + 密码,签发 JWT(默认 `AUTH_ACCESS_TOKEN_EXPIRE_MINUTES=1440`,即 24 小时)。
- `GET /api/auth/me`:校验 token 并返回当前用户公开信息。
- 后续业务请求带 `Authorization: Bearer <token>`,服务端从 token 解析 user_id 加载用户。

JWT secret 由 `AUTH_SECRET_KEY` 提供。生产部署必须使用强随机密钥，并确保所有业务请求都通过 `Authorization: Bearer <token>` 认证。

### Dev 模式(开发与测试路径)

无 `Authorization` 时,服务端回落到 dev 模式,通过请求头识别用户:

```http
X-User-Name: demo
```

默认 dev 用户:

| User | Purpose |
| --- | --- |
| `demo` | 默认演示用户 |
| `sandbox` | 前端可切换的第二个演示用户 |
| `test` | 自动化测试用户 |

### 作用域执行

- 依赖解析:`app/api/deps.py`(JWT 优先,无 token 则回落到 dev header)
- 资源归属校验:`app/services/user_scope_service.py`(`get_resume_for_user_or_404` 等)

核心业务对象都直接或间接受当前用户约束,避免跨用户读取或写入。JWT 用户和 dev 用户在数据库中是同一张 `users` 表,只是登入路径不同。

## Core Models

| Model | Purpose |
| --- | --- |
| `User` | 开发阶段用户域 |
| `Resume` | 简历原文、来源、解析状态和结构化结果 |
| `ResumeVersion` | 简历版本和针对岗位的定制版本 |
| `JobPosting` | 岗位、JD、来源 URL 和结构化结果 |
| `MatchResult` | 岗位和简历的匹配分析 |
| `ApplicationRecord` | 投递记录、阶段和下一步动作 |
| `ApplicationEvent` | 投递阶段变化事件 |
| `GeneratedArtifact` | 求职信、面试准备等生成材料 |
| `ArtifactFeedbackEvent` | 材料采纳、拒绝、稍后保存等反馈 |
| `Conversation` | AI 助手会话 |
| `Message` | 用户和助手消息 |
| `MemorySummary` | 会话摘要记忆 |
| `AgentRun` | 一次 Agent 运行记录 |
| `ToolCallLog` | 工具调用输入、输出、耗时和错误 |
| `KnowledgeBase` | 用户知识库分组 |
| `KnowledgeDocument` | 上传或粘贴的知识库文档 |
| `KnowledgeChunk` | 已切片并向量化的检索单元 |

## API Overview

### Health

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | 应用健康检查 |
| `GET` | `/health/db` | 数据库健康检查 |

### Auth

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/auth/register` | 用户名 + email + 密码注册,bcrypt 哈希,返回 JWT |
| `POST` | `/api/auth/login` | 用户名 + 密码登录,返回 JWT |
| `GET` | `/api/auth/me` | 校验 token 并返回当前用户公开信息 |

注意:auth router 的 prefix 是 `/api/auth`,**不带 `/v1`**;其它业务 API 仍走 `/api/v1`。

### Resumes

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/v1/resumes` | 创建简历 |
| `POST` | `/api/v1/resumes/upload` | 上传 PDF / DOCX / TXT / MD 并抽取文本 |
| `POST` | `/api/v1/resumes/draft-from-input` | 把简历文本喂给 LLM 起草一份简历草稿,不落库 |
| `GET` | `/api/v1/resumes` | 当前用户简历列表 |
| `GET` | `/api/v1/resumes/{resume_id}` | 简历详情 |
| `PATCH` | `/api/v1/resumes/{resume_id}` | 更新简历 |
| `DELETE` | `/api/v1/resumes/{resume_id}` | 删除简历及关联资源 |
| `POST` | `/api/v1/resumes/{resume_id}/parse` | LLM 结构化解析简历 |

### Resume Versions

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/v1/resume-versions` | 手工创建简历版本 |
| `POST` | `/api/v1/resume-versions/generate-tailored` | 针对岗位生成定制简历版本 |
| `GET` | `/api/v1/resume-versions` | 简历版本列表 |
| `GET` | `/api/v1/resume-versions/{version_id}` | 简历版本详情 |
| `PATCH` | `/api/v1/resume-versions/{version_id}` | 更新简历版本 |
| `GET` | `/api/v1/resume-versions/{version_id}/export` | 导出为 Markdown / DOCX(query `format=markdown\|docx`) |
| `GET` | `/api/v1/resumes/{resume_id}/versions` | 某份简历的版本列表 |

### Jobs

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/v1/jobs` | 创建岗位 |
| `POST` | `/api/v1/jobs/fetch-from-url` | 抓取岗位 URL 并返回预览(不落库) |
| `POST` | `/api/v1/jobs/draft-from-input` | 把 JD 文本或 URL 喂给 LLM 起草岗位草稿,不落库 |
| `GET` | `/api/v1/jobs` | 岗位列表 |
| `GET` | `/api/v1/jobs/{job_id}` | 岗位详情 |
| `PATCH` | `/api/v1/jobs/{job_id}` | 更新岗位 |
| `DELETE` | `/api/v1/jobs/{job_id}` | 删除岗位及关联资源 |
| `POST` | `/api/v1/jobs/{job_id}/parse` | LLM 结构化解析 JD |

### Matches

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/v1/matches` | 手工创建匹配结果 |
| `POST` | `/api/v1/matches/analyze` | 基于已解析 JD 和简历生成匹配分析 |
| `GET` | `/api/v1/matches` | 匹配结果列表 |
| `GET` | `/api/v1/matches/{match_id}` | 匹配结果详情 |
| `PATCH` | `/api/v1/matches/{match_id}` | 更新匹配结果 |
| `DELETE` | `/api/v1/matches/{match_id}` | 删除匹配结果 |

### Applications

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/v1/applications` | 创建投递记录 |
| `GET` | `/api/v1/applications` | 投递记录列表 |
| `GET` | `/api/v1/applications/{application_id}` | 投递记录详情 |
| `PATCH` | `/api/v1/applications/{application_id}` | 更新投递记录 |
| `DELETE` | `/api/v1/applications/{application_id}` | 删除投递记录 |
| `GET` | `/api/v1/applications/{application_id}/events` | 投递事件时间线 |
| `POST` | `/api/v1/applications/{application_id}/transition` | 阶段流转并写入事件 |

### Artifacts

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/v1/artifacts` | 手工创建材料 |
| `GET` | `/api/v1/artifacts` | 材料列表 |
| `GET` | `/api/v1/artifacts/{artifact_id}` | 材料详情 |
| `PATCH` | `/api/v1/artifacts/{artifact_id}` | 更新材料 |
| `DELETE` | `/api/v1/artifacts/{artifact_id}` | 删除材料及反馈 |
| `GET` | `/api/v1/artifacts/{artifact_id}/export` | 导出为 Markdown / DOCX(query `format=markdown\|docx`) |
| `POST` | `/api/v1/artifacts/generate-cover-letter` | 生成求职信 |
| `POST` | `/api/v1/artifacts/generate-interview-prep` | 生成面试准备 |
| `POST` | `/api/v1/artifacts/{artifact_id}/feedback` | 记录材料反馈 |
| `GET` | `/api/v1/artifacts/{artifact_id}/feedback` | 查看材料反馈 |

### Assistant And Conversations

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/v1/conversations` | 会话列表 |
| `GET` | `/api/v1/conversations/{conversation_id}/messages` | 会话消息 |
| `GET` | `/api/v1/conversations/{conversation_id}/agent-runs` | 列出会话所有 AgentRun + 嵌套 ToolCallLog(供前端可观测) |
| `PATCH` | `/api/v1/conversations/{conversation_id}` | 更新会话标题或状态 |
| `DELETE` | `/api/v1/conversations/{conversation_id}` | 删除会话 |
| `POST` | `/api/v1/assistant/run` | 非流式 Agent 运行 |
| `POST` | `/api/v1/assistant/run-stream` | SSE 流式 Agent 运行 |

### Knowledge

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/v1/knowledge/bases` | 知识库列表 |
| `POST` | `/api/v1/knowledge/bases` | 创建知识库 |
| `GET` | `/api/v1/knowledge/bases/{kb_id}` | 知识库详情 |
| `PATCH` | `/api/v1/knowledge/bases/{kb_id}` | 更新知识库 |
| `DELETE` | `/api/v1/knowledge/bases/{kb_id}` | 删除知识库 |
| `GET` | `/api/v1/knowledge/bases/{kb_id}/documents` | 文档列表 |
| `POST` | `/api/v1/knowledge/bases/{kb_id}/documents/upload` | 上传文档并索引 |
| `POST` | `/api/v1/knowledge/bases/{kb_id}/documents` | 粘贴文本并索引 |
| `GET` | `/api/v1/knowledge/documents/{document_id}` | 文档详情 |
| `GET` | `/api/v1/knowledge/documents/{document_id}/chunks` | 文档 chunk 预览 |
| `POST` | `/api/v1/knowledge/documents/{document_id}/reindex` | 重新切片并 embedding |
| `DELETE` | `/api/v1/knowledge/documents/{document_id}` | 删除文档 |

## AI Generation Services

| Service | Input | Output |
| --- | --- | --- |
| `job_parsing_service` | `job_postings.jd_text` | `job_postings.parsed_json` |
| `resume_parsing_service` | `resumes.raw_text` | `resumes.parsed_json` |
| `match_analysis_service` | parsed resume + parsed job | `match_results` row |
| `cover_letter_service` | resume + job + latest match | `generated_artifacts` row |
| `interview_prep_service` | resume + job + latest match | `generated_artifacts` row |
| `tailored_resume_service` | resume + job + latest match | `resume_versions` row |

生成服务的共同原则：

- 缺少 LLM 配置时返回清晰错误，不伪造成功结果。
- 输入对象必须属于当前用户。
- 需要结构化前置数据时显式返回 400。
- LLM 输出必须经过 JSON / schema / 内容校验后才写库。
- 定制简历 prompt 明确禁止编造不存在的经历、项目、指标、奖项、时间、技能、公司、职级或学历。

## Agent Runtime

当前 Assistant 支持两种模式：

| Mode | Description |
| --- | --- |
| `chat` | 普通求职助手对话 |
| `mock_interview` | 交互式模拟面试，每轮只提出一个问题 |

请求上下文可包含：

- `conversation_id`
- `resume_id`
- `job_posting_id`
- `application_record_id`
- `knowledge_base_id`
- `assistant_mode`

工具注册表(共 20 个,按类型分组):

| Tool | Category | Side Effect | Description |
| --- | --- | --- | --- |
| `list_user_jobs` | list | No | 查找岗位 |
| `list_user_resumes` | list | No | 查找简历 |
| `list_user_applications` | list | No | 查找投递记录 |
| `list_generated_artifacts` | list | No | 列已生成的求职信/面试材料等(紧凑列表,不返正文) |
| `read_resume` | read | No | 按 id 读取简历完整结构(parsed_json + raw_text) |
| `read_job_posting` | read | No | 按 id 读取岗位完整结构(parsed_json + jd_text) |
| `search_knowledge` | retrieval | No | 语义检索知识库 |
| `parse_resume` | parse | Yes | 触发简历 LLM 解析,把 parse_status 升级为 parsed |
| `parse_job_posting` | parse | Yes | 触发岗位 LLM 解析,填 parsed_json |
| `analyze_match` | action | Yes | 创建匹配分析 |
| `generate_cover_letter` | action | Yes | 创建求职信材料 |
| `generate_interview_prep` | action | Yes | 创建面试准备材料 |
| `generate_tailored_resume` | action | Yes | 创建定制简历版本 |
| `draft_job` | draft | No | 用户在对话里贴 JD 文本或 URL → LLM 起草岗位草稿,不落库 |
| `draft_resume` | draft | No | 用户在对话里贴简历文本 → LLM 起草简历草稿,不落库 |
| `create_job` | create | Yes | 用户确认草稿后落库岗位;可携带 `parsed_json` 一次写入 |
| `create_resume` | create | Yes | 用户确认草稿后落库简历;`content_hash` 服务端计算 |
| `create_application` | application | Yes | 创建投递记录,把简历和岗位绑定起来 |
| `update_application_stage` | application | Yes | 推进投递阶段并写一条 `stage_changed` 事件(`operator_type=assistant`) |
| `add_knowledge_text` | knowledge | Yes | 把文本存入指定知识库(**仅在用户明确要求保存时调用**,decide prompt 与 tool description 双重防御) |

SSE endpoint 会发送阶段、工具开始、工具完成、消息、错误和完成事件,前端据此展示"正在思考""正在调用工具"等运行状态。完整工具调用详情(arguments_json / result_json / error_detail)通过 `GET /api/v1/conversations/{cid}/agent-runs` 端点提供给前端可观测面板。

### Write 工具必填字段约定

`create_* / draft_* / add_* / update_*` 类工具的"用户输入"必填字段(例如 `create_job.jd_text`、`create_resume.raw_text`、`add_knowledge_text.content`、`create_application.resume_id`)在 schema 层都是 `Optional` 的,`_execute` 入口检查后返回:

```jsonc
{
  "ok": false,
  "error_class": "missing_required_field",
  "message_for_llm": "缺少必填字段: JD 正文。请用 respond_directly 向用户追问...",
  "missing_fields": ["jd_text"]
}
```

这条约定避免了"用户没贴 JD → schema 拒收 → ValidationError → repair loop → 失败"的死循环。LLM 看到业务错就用 `respond_directly` 自然追问用户那个具体字段。新增 write 工具时**必须沿用**这条约定,纯系统字段(例如前一个工具已经产出的 id)才保留 required。

## Knowledge Indexing

知识库索引流程：

```text
上传文件或粘贴文本
↓
抽取 / 清洗 raw_text
↓
写入 knowledge_documents
↓
自研 text_splitter 切片
↓
OpenAI-compatible embeddings
↓
写入 knowledge_chunks.embedding
↓
search_knowledge 使用 pgvector 检索
```

支持的文件来源：

- PDF
- DOCX
- TXT
- Markdown
- 手工粘贴文本

当前索引在 HTTP 请求内同步完成。失败时文档会保留在 `failed` 状态并记录 `error_detail`，用户修复配置后可调用 reindex。

## Migrations

生成迁移：

```powershell
uv --cache-dir .uv-cache --directory backend run alembic revision --autogenerate -m "describe schema change"
```

执行迁移：

```powershell
uv --cache-dir .uv-cache --directory backend run alembic upgrade head
```

查看当前版本：

```powershell
uv --cache-dir .uv-cache --directory backend run alembic current
```

迁移应只描述已经实现的模型变化，不提前声明未来 Agent、RAG 或评估表。

## Current Boundaries

后端当前仍不包含:

- 团队空间、企业级权限或 OAuth(JWT 已上线但仅个人作用域;`JWT_SECRET` 仍是开发占位,上线前需替换)。
- 生产级异步任务队列(知识库索引仍在 HTTP 请求内同步执行)。
- 邮件、日历、通知或真实投递集成。
- PDF 导出和模板排版(已支持简历版本 / 求职材料的 Markdown / DOCX 导出)。
- embedding 维度在线切换。
- 简历版本号并发锁或唯一约束(当前按 `max(version_no)+1` 派生)。
- GitHub Actions 已覆盖测试和构建，但还没有部署流水线。
- AgentRun token_usage 字段尚未真填(schema 已透出,等接入 token 计费时再补)。

这些边界是刻意保留的工程取舍,避免在核心求职 workflow 和 Agent 可控性尚未完全稳定前引入过多平台复杂度。
