# JobPilot

JobPilot 是一个面向求职场景的 Agentic AI Workflow 系统。当前已经完成本地基础设施、后端 FastAPI 骨架、SQLAlchemy async、Alembic，以及 Resume / JobPosting / MatchResult / ApplicationRecord 四个核心模块的最小 API 闭环。

第 8 步新增了工作流承载层第一阶段能力：

- 简历版本管理：`ResumeVersion`
- 投递状态流转记录：`ApplicationEvent`
- 投递状态流转动作：`POST /api/v1/applications/{application_id}/transition`

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

当前仍然保持阶段边界：不包含前端实现、认证登录、真实 AI/RAG、LangChain、LangGraph、自动提醒、复杂状态机、文件上传、Redis 业务逻辑或生产部署配置。

## 目录结构

```text
JobPilot/
├── backend/
│   └── README.md
├── docs/
├── frontend/
│   └── README.md
├── infra/
│   └── postgres/
│       └── init/
│           └── 001_extensions.sql
├── .env.example
├── .gitignore
├── AGENTS.md
├── compose.yaml
├── project.md
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

## 最小接口示例

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
