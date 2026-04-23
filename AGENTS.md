# JobPilot Agent Notes

## Current Stage

This repository is in step 11: minimal Resume structured parsing AI loop.

## Scope Rules

- Do not expand scope beyond the requested JD / Resume parsing AI API work.
- Keep the repository simple, runnable, and easy to explain.
- Do not add real AI capabilities beyond the existing JD structured parsing and Resume structured parsing loops.
- Do not add frontend implementation yet.
- Do not add complex backend business logic yet.
- Do not add authentication, full CRUD, RAG, LangChain, LangGraph, pgAdmin, MinIO, Nginx, CI/CD, Dockerfile, or backend containers in this stage.
- Current scope adds ResumeVersion and ApplicationEvent as workflow carrying capabilities on top of the completed Resume / JobPosting / MatchResult / ApplicationRecord minimal loops.
- Current test scope only covers the key workflow loop for ResumeVersion and Application transition; it is not a complete testing system.
- Current scope adds GeneratedArtifact as the AI output carrying layer, but still does not add real AI generation.
- Step 10 added the first real AI capability: JD structured parsing into job_postings.parsed_json.
- Current scope adds the second real AI capability: Resume structured parsing into resumes.parsed_json.
- Do not add LangChain, LangGraph, RAG, batch parsing, async queues, streaming, or other AI workflows in this stage.

## Working Style

- Prefer small, explicit files over clever abstractions.
- Keep local services reproducible with Docker Compose.
- Document only what is needed to run and understand the current stage.
- Use uv for Python environment and dependency management.
