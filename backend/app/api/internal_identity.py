"""受托身份确认入口；业务能力由后续任务按白名单显式接入。"""
from fastapi import APIRouter

from app.api.deps import DelegatedIdentityDep
from app.schemas.auth import UserPublic

router = APIRouter(prefix="/api/internal/v1/identity", tags=["internal-identity"])


@router.get("/me")
async def get_delegated_identity(identity: DelegatedIdentityDep):
    return {"user": UserPublic.model_validate(identity.user), "issuer": identity.identity.issuer,
            "subject": identity.identity.subject, "actor": identity.identity.actor,
            "scopes": sorted(identity.identity.scopes)}
