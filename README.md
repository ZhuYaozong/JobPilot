# JobPilot

JobPilot is an MVP project being prepared for a 20-day sprint. This initial step only sets up the repository structure and local infrastructure services.

## Directory Structure

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

## Start Containers

```powershell
docker compose up -d
```

## Stop Containers

```powershell
docker compose down
```

To stop containers and remove local named volumes:

```powershell
docker compose down -v
```

## View Logs

```powershell
docker compose logs -f
```

For one service:

```powershell
docker compose logs -f postgres
docker compose logs -f redis
```

## Connection Information

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

## Verify pgvector

After PostgreSQL is running, verify that the `vector` extension is installed:

```powershell
docker compose exec postgres psql -U postgres -d jobpilot -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"
```

You should see one row for the `vector` extension.
