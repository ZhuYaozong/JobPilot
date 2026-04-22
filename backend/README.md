# JobPilot Backend

JobPilot 后端当前是一个最小 FastAPI 工程。现阶段已经完成应用骨架、配置管理、PostgreSQL 异步访问、SQLAlchemy、Alembic、健康检查，以及 MVP 第一批核心业务表。

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

本轮完成：

- 新增 `Resume`、`JobPosting`、`MatchResult`、`ApplicationRecord` 四个 SQLAlchemy 模型。
- 使用 JSONB 保存简历解析结果、JD 解析结果和匹配分析中的结构化字段。
- 使用外键关联 `match_results` / `application_records` 到 `resumes` 和 `job_postings`。
- 生成并执行 Alembic 迁移，创建 MVP 第一批业务表。
- 保留已有 `users` 表和已有用户表迁移，不删除、不重命名、不重构。

本轮故意没做：

- 没有写完整 CRUD API。
- 没有写 service 层业务逻辑。
- 没有做认证、登录或权限系统。
- 没有接入 AI、RAG、LangChain 或 LangGraph。
- 没有加入 pgvector 字段。
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
│   │   └── health.py
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

未完成：

- 前端实现
- 真实 AI 集成
- RAG、LangChain 或 LangGraph
- 认证登录
- 完整 CRUD
- service 层业务逻辑
- 生产 Dockerfile、Nginx 或 CI/CD
