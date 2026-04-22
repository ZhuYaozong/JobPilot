# JobPilot Backend

JobPilot 后端当前是一个最小 FastAPI 工程。现阶段已经完成应用骨架、配置管理、PostgreSQL 异步访问、SQLAlchemy、Alembic、健康检查、MVP 第一批核心业务表，以及 Resume / JobPosting / MatchResult / ApplicationRecord 模块的最小 API 闭环。

## 环境要求

- 使用 `uv` 管理 Python 环境和依赖
- 使用仓库根目录的 `compose.yaml` 启动本地 PostgreSQL 和 Redis

## 安装依赖

在仓库根目录执行：

```powershell
uv --directory backend sync
```

依赖由 `pyproject.toml` 和 `uv.lock` 管理，不使用 `requirements.txt` 作为主要依赖来源。

如果本机无法访问默认 uv 缓存目录，可以使用仓库内缓存：

```powershell
uv --cache-dir .uv-cache --directory backend sync
```

## 启动 FastAPI

```powershell
uv --directory backend run uvicorn app.main:app --reload
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

如果默认 uv 缓存目录不可用：

```powershell
uv --cache-dir .uv-cache --directory backend run uvicorn app.main:app --reload
```

## 执行 Alembic 迁移

模型变化后生成迁移：

```powershell
uv --directory backend run alembic revision --autogenerate -m "create core business tables"
```

执行迁移：

```powershell
uv --directory backend run alembic upgrade head
```

查看当前迁移版本：

```powershell
uv --directory backend run alembic current
```

如果默认 uv 缓存目录不可用，可以给以上命令加上 `--cache-dir .uv-cache`。

## 当前核心表

- `users`：第 2 步留下的最小用户表，用来验证 SQLAlchemy 和 Alembic 迁移链路。
- `resumes`：保存简历文本、来源、解析状态、结构化解析结果和内容哈希。
- `job_postings`：保存公司、岗位、城市、JD 原文、来源链接、解析结果和岗位状态。
- `match_results`：保存某份简历和某个岗位之间的匹配分数、优势、劣势、缺失关键词和建议。
- `application_records`：保存某份简历对某个岗位的投递/跟进状态、渠道、下一步动作和备注。

## Resume API

当前 Resume 模块支持最小闭环：

- 创建简历：`POST /api/v1/resumes`
- 简历列表：`GET /api/v1/resumes?limit=20&offset=0`
- 简历详情：`GET /api/v1/resumes/{resume_id}`
- 更新简历：`PATCH /api/v1/resumes/{resume_id}`

列表接口默认按 `created_at DESC` 返回。当前不支持删除、搜索、复杂过滤或文件上传。

### 调用示例

创建简历：

```powershell
curl.exe -X POST http://localhost:8000/api/v1/resumes `
  -H "Content-Type: application/json" `
  -d "{\"title\":\"后端开发简历\",\"raw_text\":\"熟悉 FastAPI、PostgreSQL 和 SQLAlchemy。\",\"content_hash\":\"demo-resume-hash-001\",\"source_type\":\"manual\"}"
```

查看列表：

```powershell
curl.exe "http://localhost:8000/api/v1/resumes?limit=20&offset=0"
```

查看详情：

```powershell
curl.exe http://localhost:8000/api/v1/resumes/1
```

更新简历：

```powershell
curl.exe -X PATCH http://localhost:8000/api/v1/resumes/1 `
  -H "Content-Type: application/json" `
  -d "{\"title\":\"后端开发简历 v2\",\"parse_status\":\"parsed\",\"parsed_json\":{\"skills\":[\"FastAPI\",\"PostgreSQL\",\"SQLAlchemy\"]}}"
```

## JobPosting API

当前 JobPosting 模块支持最小闭环：

- 创建岗位：`POST /api/v1/jobs`
- 岗位列表：`GET /api/v1/jobs?limit=20&offset=0`
- 岗位详情：`GET /api/v1/jobs/{job_id}`
- 更新岗位：`PATCH /api/v1/jobs/{job_id}`

列表接口默认按 `created_at DESC` 返回。当前不支持删除、搜索、复杂过滤或排序。

### 调用示例

创建岗位：

```powershell
curl.exe -X POST http://localhost:8000/api/v1/jobs `
  -H "Content-Type: application/json" `
  -d "{\"company_name\":\"示例科技\",\"job_title\":\"后端开发工程师\",\"city\":\"上海\",\"source_url\":\"https://example.com/jobs/backend\",\"jd_text\":\"负责 FastAPI 后端服务、PostgreSQL 数据建模和接口开发。\"}"
```

查看列表：

```powershell
curl.exe "http://localhost:8000/api/v1/jobs?limit=20&offset=0"
```

查看详情：

```powershell
curl.exe http://localhost:8000/api/v1/jobs/1
```

更新岗位：

```powershell
curl.exe -X PATCH http://localhost:8000/api/v1/jobs/1 `
  -H "Content-Type: application/json" `
  -d "{\"status\":\"paused\",\"parsed_json\":{\"skills\":[\"FastAPI\",\"PostgreSQL\",\"SQLAlchemy\"]}}"
```

## MatchResult API

当前 MatchResult 模块支持最小闭环：

- 创建匹配记录：`POST /api/v1/matches`
- 匹配记录列表：`GET /api/v1/matches?limit=20&offset=0`
- 匹配记录详情：`GET /api/v1/matches/{match_id}`
- 更新匹配记录：`PATCH /api/v1/matches/{match_id}`

创建匹配记录时需要传入已有的 `resume_id` 和 `job_posting_id`。当前 MatchResult 只是手工写入和更新的结构化记录，不包含真实 AI 匹配分析、自动打分或自动建议生成。

列表接口默认按 `created_at DESC` 返回。当前不支持删除、搜索、复杂过滤或排序。

### 调用示例

创建匹配记录：

```powershell
curl.exe -X POST http://localhost:8000/api/v1/matches `
  -H "Content-Type: application/json" `
  -d "{\"resume_id\":1,\"job_posting_id\":1,\"overall_score\":82.5,\"strengths\":[\"FastAPI 经验匹配\",\"熟悉 PostgreSQL\"],\"weaknesses\":[\"缺少大型系统经验\"],\"missing_keywords\":[\"Kubernetes\"],\"suggestions\":[\"补充异步任务和部署经验\"]}"
```

查看列表：

```powershell
curl.exe "http://localhost:8000/api/v1/matches?limit=20&offset=0"
```

查看详情：

```powershell
curl.exe http://localhost:8000/api/v1/matches/1
```

更新匹配记录：

```powershell
curl.exe -X PATCH http://localhost:8000/api/v1/matches/1 `
  -H "Content-Type: application/json" `
  -d "{\"overall_score\":88.0,\"suggestions\":[\"突出 FastAPI 项目经验\",\"补充 PostgreSQL 调优经历\"]}"
```

## ApplicationRecord API

当前 ApplicationRecord 模块支持最小闭环：

- 创建投递记录：`POST /api/v1/applications`
- 投递记录列表：`GET /api/v1/applications?limit=20&offset=0`
- 投递记录详情：`GET /api/v1/applications/{application_id}`
- 更新投递记录：`PATCH /api/v1/applications/{application_id}`

创建投递记录时需要传入已有的 `resume_id` 和 `job_posting_id`。当前 ApplicationRecord 只是手工写入和更新的投递/跟进记录，不包含自动提醒、状态机流转或真实业务自动化逻辑。

列表接口默认按 `created_at DESC` 返回。当前不支持删除、搜索、复杂过滤或排序。

### 调用示例

创建投递记录：

```powershell
curl.exe -X POST http://localhost:8000/api/v1/applications `
  -H "Content-Type: application/json" `
  -d "{\"resume_id\":1,\"job_posting_id\":1,\"current_stage\":\"applied\",\"apply_channel\":\"boss\",\"applied_at\":\"2026-04-22T10:00:00+08:00\",\"next_action\":\"三天后跟进\",\"next_action_at\":\"2026-04-25T10:00:00+08:00\",\"notes\":\"已投递，等待 HR 回复\"}"
```

查看列表：

```powershell
curl.exe "http://localhost:8000/api/v1/applications?limit=20&offset=0"
```

查看详情：

```powershell
curl.exe http://localhost:8000/api/v1/applications/1
```

更新投递记录：

```powershell
curl.exe -X PATCH http://localhost:8000/api/v1/applications/1 `
  -H "Content-Type: application/json" `
  -d "{\"current_stage\":\"interview\",\"next_action\":\"准备一面\",\"notes\":\"HR 已约技术面\"}"
```

本阶段完成：

- 新增 `Resume`、`JobPosting`、`MatchResult`、`ApplicationRecord` 四个 SQLAlchemy 模型。
- 使用 JSONB 保存简历解析结果、JD 解析结果和匹配分析中的结构化字段。
- 使用外键关联 `match_results` / `application_records` 到 `resumes` 和 `job_postings`。
- 生成并执行 Alembic 迁移，创建 MVP 第一批业务表。
- 保留已有 `users` 表和已有用户表迁移，不删除、不重命名、不重构。
- 新增 Resume 的 Pydantic schemas。
- 新增 Resume 的创建、列表、详情、更新接口。
- 新增 JobPosting 的 Pydantic schemas。
- 新增 JobPosting 的创建、列表、详情、更新接口。
- 新增 MatchResult 的 Pydantic schemas。
- 新增 MatchResult 的创建、列表、详情、更新接口。
- 创建 MatchResult 时校验 `resume_id` 和 `job_posting_id` 是否存在。
- 新增 ApplicationRecord 的 Pydantic schemas。
- 新增 ApplicationRecord 的创建、列表、详情、更新接口。
- 创建 ApplicationRecord 时校验 `resume_id` 和 `job_posting_id` 是否存在。

本阶段故意没做：

- 没有写完整 CRUD API。
- 没有写 delete 接口。
- 没有写 service 层业务逻辑。
- 没有做认证、登录或权限系统。
- 没有接入 AI、RAG、LangChain 或 LangGraph。
- 没有做真实 AI 匹配分析、自动打分或自动建议生成。
- 没有做自动提醒、状态机流转或真实业务自动化逻辑。
- 没有加入 pgvector 字段。
- 没有写文件上传或对象存储。
- 没有写 Redis 业务逻辑。
- 没有写前端实现。

## 目录结构

```text
backend/
├── alembic/
│   ├── versions/
│   ├── env.py
│   ├── README
│   └── script.py.mako
├── app/
│   ├── api/
│   │   ├── applications.py
│   │   ├── health.py
│   │   ├── jobs.py
│   │   ├── matches.py
│   │   └── resumes.py
│   ├── core/
│   │   └── config.py
│   ├── db/
│   │   ├── base.py
│   │   └── session.py
│   ├── models/
│   │   ├── application_record.py
│   │   ├── job_posting.py
│   │   ├── match_result.py
│   │   ├── resume.py
│   │   └── user.py
│   ├── schemas/
│   │   ├── application_record.py
│   │   ├── job_posting.py
│   │   ├── match_result.py
│   │   └── resume.py
│   └── main.py
├── .env.example
├── alembic.ini
├── pyproject.toml
├── README.md
└── uv.lock
```

## 当前范围

已完成：

- FastAPI 应用入口
- `GET /health`
- `GET /health/db`
- pydantic-settings 配置管理
- SQLAlchemy async engine 和 session factory
- Alembic 读取模型 metadata 并执行迁移
- 一个最小 `User` 模型
- 第一批 MVP 核心业务模型和数据库表
- Resume 模块最小 API 闭环
- JobPosting 模块最小 API 闭环
- MatchResult 模块最小 API 闭环
- ApplicationRecord 模块最小 API 闭环

未完成：

- 前端实现
- 真实 AI 集成
- RAG、LangChain 或 LangGraph
- 认证登录
- 完整 CRUD 和删除接口
- 自动提醒和状态机引擎
- service 层业务逻辑
- 生产 Dockerfile、Nginx 或 CI/CD
