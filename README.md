# JobPilot

JobPilot 是一个面向求职流程管理的 MVP 项目。当前已经完成本地基础设施、后端 FastAPI 骨架、核心业务表，以及四个核心业务模块的最小 API 闭环。

当前后端已支持：

- 健康检查：`GET /health`、`GET /health/db`
- 简历模块：`/api/v1/resumes`
- 岗位模块：`/api/v1/jobs`
- 匹配结果模块：`/api/v1/matches`
- 投递记录模块：`/api/v1/applications`

当前仍然保持 MVP 范围：不包含前端实现、认证登录、AI/RAG、自动提醒、状态机流转、文件上传或生产部署配置。

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

## 停止本地服务

```powershell
docker compose down
```

停止容器并删除本地命名卷：

```powershell
docker compose down -v
```

## 查看日志

```powershell
docker compose logs -f
```

查看单个服务：

```powershell
docker compose logs -f postgres
docker compose logs -f redis
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
