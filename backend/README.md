# JobPilot Backend

JobPilot 后端是面向求职场景的 Agentic AI Workflow 系统的最小承载层。当前已经完成应用骨架、配置管理、PostgreSQL 异步访问、SQLAlchemy、Alembic、健康检查，以及 Resume / JobPosting / MatchResult / ApplicationRecord 四个核心模块的最小 API 闭环。

第 8 步新增了两类工作流能力：

- `ResumeVersion`：保存原始简历和面向岗位的定制版本。
- `ApplicationEvent`：记录投递阶段变化等工作流事件。

第 8.5 步新增了最小自动化测试底座，当前只覆盖关键 workflow 闭环，不代表完整测试体系。

第 9 步新增了 AI 产物承载层 `GeneratedArtifact`，用于保存手工写入或未来 AI 生成的求职材料产物；当前仍未接入真实 AI 生成。

当前仍不包含真实 AI 生成、RAG、LangChain、LangGraph、认证登录、前端、文件上传、Redis 业务逻辑、自动提醒或复杂状态机。

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
- `POST http://localhost:8000/api/v1/jobs`
- `GET http://localhost:8000/api/v1/jobs`
- `GET http://localhost:8000/api/v1/jobs/{job_id}`
- `PATCH http://localhost:8000/api/v1/jobs/{job_id}`
- `POST http://localhost:8000/api/v1/matches`
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

测试会连接当前后端配置中的 PostgreSQL 数据库。由于当前项目还没有独立测试数据库配置，测试通过 API 创建带 `pytest-jobpilot-*` 唯一标记的前置数据，不依赖已有人工数据或固定 id。当前测试不会覆盖完整系统，只覆盖关键 workflow 和 AI 产物承载闭环。

## 当前核心表

- `users`：第 2 步留下的最小用户表，用来验证 SQLAlchemy 和 Alembic 迁移链路。
- `resumes`：保存简历文本、来源、解析状态、结构化解析结果和内容哈希。
- `job_postings`：保存公司、岗位、城市、JD 原文、来源链接、解析结果和岗位状态。
- `match_results`：保存某份简历和某个岗位之间的匹配分数、优势、劣势、缺失关键词和建议。
- `application_records`：保存某份简历对某个岗位的投递/跟进状态、渠道、下一步动作和备注。
- `resume_versions`：保存简历版本、关联岗位、版本内容、来源类型和变更摘要。
- `application_events`：保存投递记录的阶段变化事件、操作来源、附加 payload 和备注。
- `generated_artifacts`：保存求职信、简历摘要等 AI 产物承载记录，目前只支持手工写入和更新。

## GeneratedArtifact API

当前 GeneratedArtifact 模块支持最小闭环：

- 创建产物：`POST /api/v1/artifacts`
- 产物列表：`GET /api/v1/artifacts?limit=20&offset=0`
- 产物详情：`GET /api/v1/artifacts/{artifact_id}`
- 更新产物：`PATCH /api/v1/artifacts/{artifact_id}`

创建或更新时，`resume_id`、`job_posting_id`、`application_record_id` 至少要有一个非空；如果传入这些关联 id，会校验对应业务对象是否存在。当前不做真实 AI 生成、模板渲染、PDF/DOCX 导出、删除、复杂搜索、复杂过滤或复杂排序。

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

当前列表接口默认按 `created_at DESC` 返回。当前不支持删除、复杂搜索、复杂过滤或复杂排序。

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

## 本阶段故意没做

- 没有接入真实 AI 自动生成逻辑。
- 没有做模板渲染、PDF/DOCX 导出或产物删除接口。
- 没有引入 LangChain、LangGraph 或 RAG。
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
│   │   └── 768a3418a62d_create_users_table.py
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
│   ├── models/
│   │   ├── application_event.py
│   │   ├── application_record.py
│   │   ├── generated_artifact.py
│   │   ├── job_posting.py
│   │   ├── match_result.py
│   │   ├── resume.py
│   │   ├── resume_version.py
│   │   └── user.py
│   ├── schemas/
│   │   ├── application_event.py
│   │   ├── application_record.py
│   │   ├── generated_artifact.py
│   │   ├── job_posting.py
│   │   ├── match_result.py
│   │   ├── resume.py
│   │   └── resume_version.py
│   ├── services/
│   │   ├── __init__.py
│   │   └── application_transition_service.py
│   └── main.py
├── tests/
│   ├── conftest.py
│   ├── test_application_transition.py
│   ├── test_generated_artifacts.py
│   └── test_resume_versions.py
├── .env.example
├── alembic.ini
├── pyproject.toml
├── README.md
└── uv.lock
```
