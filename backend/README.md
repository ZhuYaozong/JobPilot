# JobPilot Backend

This backend is a minimal FastAPI skeleton for the JobPilot MVP. The current stage only wires the application, configuration, PostgreSQL async access, SQLAlchemy, Alembic, and health checks.

## Requirements

- Python managed through `uv`
- Local PostgreSQL and Redis from the root `compose.yaml`

## Install Dependencies

From the repository root:

```powershell
uv --directory backend sync
```

Dependencies are managed in `pyproject.toml` and `uv.lock`. Do not use `requirements.txt` as the primary dependency source.

If your local environment cannot access the default uv cache directory, add a workspace cache:

```powershell
uv --cache-dir .uv-cache --directory backend sync
```

## Run FastAPI

```powershell
uv --directory backend run uvicorn app.main:app --reload
```

Then open:

- `GET http://localhost:8000/health`
- `GET http://localhost:8000/health/db`

## Run Alembic Migrations

Generate a migration after model changes:

```powershell
uv --directory backend run alembic revision --autogenerate -m "create users table"
```

Apply migrations:

```powershell
uv --directory backend run alembic upgrade head
```

## Directory Structure

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
│   │   └── user.py
│   ├── schemas/
│   └── main.py
├── .env.example
├── alembic.ini
├── pyproject.toml
├── README.md
└── uv.lock
```

## Current Scope

Done:

- FastAPI application entry
- `GET /health`
- `GET /health/db`
- pydantic-settings configuration
- SQLAlchemy async engine and session factory
- Alembic configured with model metadata
- One minimal `User` model to verify migrations

Not done:

- Frontend implementation
- Real AI integration
- RAG, LangChain, or LangGraph
- Authentication
- Full CRUD
- Production Dockerfile, Nginx, or CI/CD
