"""绑定只接受双 Bearer 与显式确认；整个路由对验证错误输入脱敏。"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from app.api.deps import get_delegated_verifier, get_binding_local_credential, get_binding_external_token
from app.db.session import AsyncSessionLocal
from app.schemas.external_binding import BindingResponse, ChallengeRequest, ChallengeResponse, ConfirmRequest
from app.services.external_binding_service import create_binding_challenge, confirm_external_binding, prepare_binding

logger = logging.getLogger(__name__)


class SensitiveBindingRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()
        async def handler(request):
            try:
                response = await original(request)
            except RequestValidationError:
                # errors() 可能含 input 或异常上下文，不能直接序列化给客户端。
                response = JSONResponse(status_code=422, content={"detail": "绑定请求格式无效"})
            except HTTPException as error:
                response = JSONResponse(status_code=error.status_code, content={"detail": error.detail}, headers=error.headers)
            except Exception as error:
                # 未知故障仍为 500 并告警；不把异常消息/参数中的潜在凭据写入日志。
                logger.error("绑定服务内部异常，异常类型：%s", type(error).__name__)
                response = JSONResponse(status_code=500, content={"detail": "绑定服务内部错误"})
            response.headers["Cache-Control"] = "no-store"
            return response
        return handler


router = APIRouter(prefix="/api/auth/external-bindings", tags=["external-bindings"], route_class=SensitiveBindingRoute)


def get_binding_session_factory():
    return AsyncSessionLocal


@router.post("/challenges", response_model=ChallengeResponse, status_code=201)
async def create_challenge(body: ChallengeRequest,
    credential=Depends(get_binding_local_credential), token=Depends(get_binding_external_token),
    verifier=Depends(get_delegated_verifier), factory=Depends(get_binding_session_factory)):
    identity, snapshot = await prepare_binding(factory, credential, token, body.password.get_secret_value(), verifier, "create")
    return await create_binding_challenge(factory, credential, identity, snapshot)


@router.post("/confirm", response_model=BindingResponse)
async def confirm_binding(body: ConfirmRequest,
    credential=Depends(get_binding_local_credential), token=Depends(get_binding_external_token),
    verifier=Depends(get_delegated_verifier), factory=Depends(get_binding_session_factory)):
    identity, snapshot = await prepare_binding(factory, credential, token, body.password.get_secret_value(), verifier, "confirm")
    return await confirm_external_binding(factory, credential, identity, snapshot,
        body.challenge_id, body.challenge_secret.get_secret_value())
