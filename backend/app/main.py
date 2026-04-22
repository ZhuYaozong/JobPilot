from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.jobs import router as jobs_router
from app.api.matches import router as matches_router
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
