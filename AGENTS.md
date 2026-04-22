# JobPilot Agent Notes

## Current Stage

This repository is in step 8.5: minimal backend automated test loop.

## Scope Rules

- Do not expand scope beyond the requested minimal backend automated test work.
- Keep the repository simple, runnable, and easy to explain.
- Do not add real AI integration yet.
- Do not add frontend implementation yet.
- Do not add complex backend business logic yet.
- Do not add authentication, full CRUD, RAG, LangChain, LangGraph, pgAdmin, MinIO, Nginx, CI/CD, Dockerfile, or backend containers in this stage.
- Current scope adds ResumeVersion and ApplicationEvent as workflow carrying capabilities on top of the completed Resume / JobPosting / MatchResult / ApplicationRecord minimal loops.
- Current test scope only covers the key workflow loop for ResumeVersion and Application transition; it is not a complete testing system.

## Working Style

- Prefer small, explicit files over clever abstractions.
- Keep local services reproducible with Docker Compose.
- Document only what is needed to run and understand the current stage.
- Use uv for Python environment and dependency management.
