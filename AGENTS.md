# JobPilot Agent Notes

## Current Stage

This repository is in step 26: product-oriented homepage and navigation refactor.

## Scope Rules

- Do not expand scope beyond the requested JD / Resume parsing, MatchResult AI analysis, Cover Letter draft generation, Interview Prep generation, GeneratedArtifact feedback API work, and the current frontend skeleton initialization.
- Keep the repository simple, runnable, and easy to explain.
- Do not add real AI capabilities beyond the existing JD structured parsing, Resume structured parsing, MatchResult AI analysis, Cover Letter draft generation, and Interview Prep generation loops.
- Current scope keeps the existing `frontend/` Vue 3 product shell and allows a pure frontend cleanup focused on Chinese-first copy and controlled list areas.
- Current scope does not allow implementing a complete frontend business loop, full CRUD UI, frontend auth, complex state management, real chat agent behavior, streaming, or knowledge retrieval.
- Do not add complex backend business logic yet.
- Do not add authentication, full CRUD, RAG, LangChain, LangGraph, pgAdmin, MinIO, Nginx, CI/CD, Dockerfile, or backend containers in this stage.
- Current scope adds ResumeVersion and ApplicationEvent as workflow carrying capabilities on top of the completed Resume / JobPosting / MatchResult / ApplicationRecord minimal loops.
- Current test scope only covers the key workflow loop for ResumeVersion and Application transition; it is not a complete testing system.
- Current scope adds GeneratedArtifact as the AI output carrying layer, but still does not add real AI generation.
- Step 10 added the first real AI capability: JD structured parsing into job_postings.parsed_json.
- Step 11 added the second real AI capability: Resume structured parsing into resumes.parsed_json.
- Step 12 added the third real AI capability: MatchResult generation from structured Resume and structured JD.
- Step 13 added the first generation capability: Cover Letter draft generation into generated_artifacts.
- Step 14 added the second generation capability: Interview Prep generation into generated_artifacts.
- Step 15 added the minimal feedback loop for generated_artifacts through artifact_feedback_events.
- Current scope adds the minimal frontend product skeleton for Workflow Workspace and AI Copilot Layer without changing backend behavior.
- Step 24 added a minimal user scope via dev-only current-user headers, isolated pytest data from demo data, and made recent-first / limit rules explicit in backend lists.
- Step 25 focuses only on frontend Chinese copy cleanup and multi-page list containment; it does not modify backend user scope, models, schemas, APIs, or tests.
- Step 26 focuses only on product-oriented homepage and navigation refactor; it turns the frontend entry from a system explanation console into a user task entry while keeping existing routes, workflow pages, backend APIs, and user scope logic unchanged.
- Do not add a full evaluation system, feedback aggregation, dashboards, automatic regeneration, or status mutation from feedback in this stage.
- Do not add LangChain, LangGraph, RAG, batch parsing, async queues, streaming, or other AI workflows in this stage.

## Working Style

- Prefer small, explicit files over clever abstractions.
- Keep local services reproducible with Docker Compose.
- Document only what is needed to run and understand the current stage.
- Use uv for Python environment and dependency management.
