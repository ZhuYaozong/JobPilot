from fastapi import FastAPI

from app.api.application_events import router as application_events_router
from app.api.applications import router as applications_router
from app.api.artifacts import router as artifacts_router
from app.api.assistant import router as assistant_router
from app.api.conversations import router as conversations_router
from app.api.health import router as health_router
from app.api.jobs import router as jobs_router
from app.api.knowledge import router as knowledge_router
from app.api.matches import router as matches_router
from app.api.resume_versions import router as resume_versions_router
from app.api.resumes import router as resumes_router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    debug=settings.app_debug,
)

app.include_router(health_router)
app.include_router(resumes_router)
app.include_router(jobs_router)
app.include_router(matches_router)
app.include_router(applications_router)
app.include_router(resume_versions_router)
app.include_router(application_events_router)
app.include_router(artifacts_router)
app.include_router(conversations_router)
app.include_router(assistant_router)
app.include_router(knowledge_router)
