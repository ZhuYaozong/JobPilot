from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/db")
async def database_health(db: AsyncSession = Depends(get_db)) -> dict[str, int | str]:
    result = await db.execute(text("SELECT 1"))
    return {"status": "ok", "database": result.scalar_one()}
