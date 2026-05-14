# JobPilot Backend

`backend/` 是 JobPilot 的后端服务，负责业务 API、数据库模型、LLM 生成服务、LangGraph Agent Runtime、RAG 知识库和工具调用审计。它不是一个只暴露 CRUD 的后台，而是围绕求职流程构建的可追踪 AI workflow 层。

当前后端已经完成：

- 岗位、简历、匹配、材料、投递的核心业务 API。
- JD / Resume 结构化解析、匹配分析、求职信、面试准备和定制简历生成。
- Conversation / Message / AgentRun / ToolCallLog 的 Agent 数据层。
- LangGraph 1.x 工作流和基于 `langchain-core` 的工具抽象。
- SSE 流式 Assistant。
- KnowledgeBase / KnowledgeDocument / KnowledgeChunk 数据层。
- 自研文本切片、OpenAI-compatible embedding client、pgvector 检索。
- 开发阶段用户作用域隔离。

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

## User Scope

当前没有正式登录系统。后端通过 dev-only 请求头识别用户：

```http
X-User-Name: demo
```

默认用户：

| User | Purpose |
| --- | --- |
| `demo` | 默认演示用户 |
| `sandbox` | 前端可切换的第二个演示用户 |
| `test` | 自动化测试用户 |

作用域规则集中在：

- `app/api/deps.py`
- `app/services/user_scope_service.py`

核心业务对象都直接或间接受当前用户约束，避免跨用户读取或写入。

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

### Resumes

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/v1/resumes` | 创建简历 |
| `POST` | `/api/v1/resumes/upload` | 上传 PDF / DOCX / TXT / MD 并抽取文本 |
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
| `GET` | `/api/v1/resumes/{resume_id}/versions` | 某份简历的版本列表 |

### Jobs

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/v1/jobs` | 创建岗位 |
| `POST` | `/api/v1/jobs/fetch-from-url` | 抓取岗位 URL 并返回预览 |
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
| `POST` | `/api/v1/artifacts/generate-cover-letter` | 生成求职信 |
| `POST` | `/api/v1/artifacts/generate-interview-prep` | 生成面试准备 |
| `POST` | `/api/v1/artifacts/{artifact_id}/feedback` | 记录材料反馈 |
| `GET` | `/api/v1/artifacts/{artifact_id}/feedback` | 查看材料反馈 |

### Assistant And Conversations

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/v1/conversations` | 会话列表 |
| `GET` | `/api/v1/conversations/{conversation_id}/messages` | 会话消息 |
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

工具注册表：

| Tool | Side Effect | Description |
| --- | --- | --- |
| `list_user_jobs` | No | 查找岗位 |
| `list_user_resumes` | No | 查找简历 |
| `list_user_applications` | No | 查找投递记录 |
| `search_knowledge` | No | 语义检索知识库 |
| `analyze_match` | Yes | 创建匹配分析 |
| `generate_cover_letter` | Yes | 创建求职信材料 |
| `generate_interview_prep` | Yes | 创建面试准备材料 |
| `generate_tailored_resume` | Yes | 创建定制简历版本 |

SSE endpoint 会发送阶段、工具开始、工具完成、消息、错误和完成事件，前端据此展示“正在思考”“正在调用工具”等运行状态。

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

后端当前仍不包含：

- 正式认证、注册、JWT、团队权限或 OAuth。
- 生产级异步任务队列。
- 邮件、日历、通知或真实投递集成。
- PDF / DOCX 导出和模板排版。
- embedding 维度在线切换。
- 简历版本号并发锁或唯一约束。
- 完整 CI/CD 发布流水线。

这些边界是刻意保留的工程取舍，避免在核心求职 workflow 和 Agent 可控性尚未完全稳定前引入过多平台复杂度。
