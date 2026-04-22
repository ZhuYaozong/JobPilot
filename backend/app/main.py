from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.resumes import router as resumes_router
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    debug=settings.app_debug,
)

app.include_router(health_router)
app.include_router(resumes_router)
