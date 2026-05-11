from fastapi import APIRouter

from app.api.deps import CurrentUserDep, DbSession
from app.schemas.assistant import AssistantRunRequest, AssistantRunResponse
from app.services.assistant_service import run_assistant_turn

router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])


@router.post("/run", response_model=AssistantRunResponse)
async def run_assistant(
    payload: AssistantRunRequest,
    db: DbSession,
    current_user: CurrentUserDep,
) -> AssistantRunResponse:
    return await run_assistant_turn(db, current_user, payload)
