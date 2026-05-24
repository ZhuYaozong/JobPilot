# Security Policy

JobPilot is currently a personal open-source project in active development.

## Reporting a Vulnerability

Please do not open a public issue for sensitive security reports. Report the
problem privately to the repository owner, or use GitHub private vulnerability
reporting if it is enabled for the repository.

Include:

- affected commit or version
- steps to reproduce
- impact and affected data
- any relevant logs or proof of concept

## Production Notes

Before deploying JobPilot outside local development:

- set `APP_ENV=production`
- set `APP_DEBUG=false`
- set `AUTH_DEV_MODE=false`
- replace `AUTH_SECRET_KEY` with a long random secret
- rotate any LLM, embedding, database, and Redis credentials that were used in
  local testing
- do not expose the default PostgreSQL or Redis ports without network controls

The default credentials in `.env.example` and `compose.yaml` are for local
development only.
