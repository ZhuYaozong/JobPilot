"""绑定接口不允许请求自报账号归属；敏感字段禁止进入 repr。"""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class ChallengeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    password: SecretStr = Field(min_length=1, max_length=128)


class ConfirmRequest(ChallengeRequest):
    challenge_id: UUID
    challenge_secret: SecretStr = Field(min_length=43, max_length=43)
    confirm: Literal[True]

    @field_validator("confirm", mode="before")
    @classmethod
    def require_explicit_true(cls, value):
        # Python 中 1 == True，不能让整数或字符串代替明确的 JSON 布尔值。
        if value is not True:
            raise ValueError("必须明确确认绑定")
        return value


class ChallengeResponse(BaseModel):
    challenge_id: UUID
    challenge_secret: str = Field(repr=False)
    expires_at: datetime
    user_id: int
    username: str
    issuer: str
    subject: str


class BindingResponse(BaseModel):
    status: Literal["bound"] = "bound"
    binding_id: int
    user_id: int
    issuer: str
    subject: str
    audit_id: UUID
