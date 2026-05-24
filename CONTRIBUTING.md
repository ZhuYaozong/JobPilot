# Contributing

Thanks for taking an interest in JobPilot. This project is still moving quickly,
so small, focused contributions are the easiest to review.

## Development Setup

```powershell
Copy-Item .env.example .env
Copy-Item backend/.env.example backend/.env
Copy-Item frontend/.env.example frontend/.env
docker compose up -d
uv --cache-dir .uv-cache --directory backend sync
uv --cache-dir .uv-cache --directory backend run alembic upgrade head
cd frontend
npm install
```

## Checks

Run these before opening a pull request:

```powershell
uv --cache-dir .uv-cache --directory backend run pytest
cd frontend
npm run build
```

The agent eval runner is useful for behavior changes:

```powershell
uv --cache-dir .uv-cache --directory backend run python -m app.eval.cli
```

## Pull Requests

- Keep changes scoped to one problem.
- Add or update tests when behavior changes.
- Update README or module docs when setup, API behavior, or product scope changes.
- Do not commit real `.env` files, API keys, personal resumes, or job application data.
- Prefer existing service/API/component patterns over new abstractions unless the
  existing structure is genuinely blocking the change.

## License

By contributing, you agree that your contributions will be licensed under the
MIT License.
