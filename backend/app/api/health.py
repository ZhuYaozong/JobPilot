from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import DbSession

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/db")
async def database_health(db: DbSession) -> dict[str, int | str]:
    result = await db.execute(text("SELECT 1"))
    return {"status": "ok", "database": result.scalar_one()}
