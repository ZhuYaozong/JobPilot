"""固定身份源的受托访问令牌验证；不从 token 的 URL 或用户名建立信任。"""
import asyncio
from dataclasses import dataclass
import json
import time

from fastapi import HTTPException
import httpx
from jose import JWTError, jwt
from jose.utils import base64url_decode

from app.core.config import Settings


@dataclass(frozen=True)
class VerifiedExternalIdentity:
    issuer: str
    subject: str
    actor: str
    scopes: frozenset[str]


def unauthorized():
    return HTTPException(401, "受托令牌无效或已失效", headers={"WWW-Authenticate": "Bearer"})


class DelegatedTokenVerifier:
    def __init__(self, config: Settings):
        self.config = config
        self._keys = {}
        self._expires = 0.0
        self._unknown_refresh = float("-inf")
        self._lock = asyncio.Lock()

    async def _json(self, client, method, url, **kwargs):
        # 不跟随重定向、不使用继承代理，限制响应体，错误不回显 token/密钥。
        try:
            async with client.stream(method, url, **kwargs) as response:
                if response.status_code != 200:
                    raise ValueError("identity service status")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > 131072:
                        raise ValueError("identity response too large")
                value = json.loads(body)
                if not isinstance(value, dict):
                    raise ValueError("identity response shape")
                return value
        except (httpx.HTTPError, ValueError, UnicodeError, RecursionError):
            raise HTTPException(503, "身份服务暂不可用") from None

    async def _key(self, client, kid):
        async with self._lock:
            now = time.monotonic()
            expired = now >= self._expires
            if not expired and kid in self._keys:
                return self._keys[kid]
            if not expired:
                # 陌生 kid 最多每五秒触发一次额外刷新，避免任意 token 打爆 JWKS。
                if now - self._unknown_refresh < 5:
                    raise unauthorized()
                self._unknown_refresh = now
            document = await self._json(client, "GET", self.config.delegated_jwks_url)
            keys = {}
            try:
                candidates = document["keys"]
                if not isinstance(candidates, list) or not 1 <= len(candidates) <= 32:
                    raise ValueError("JWKS shape")
                for value in candidates:
                    if not isinstance(value, dict):
                        raise ValueError("JWK shape")
                    if value.get("kty") != "RSA" or value.get("use", "sig") != "sig" or value.get("alg", "RS256") != "RS256":
                        continue
                    key_id = value["kid"]
                    bits = int.from_bytes(base64url_decode(value["n"].encode()), "big").bit_length()
                    if not isinstance(key_id, str) or not 1 <= len(key_id) <= 128 or key_id in keys or not 2048 <= bits <= 8192 or not value.get("e"):
                        raise ValueError("JWK identity or strength")
                    # 仅保留所需公开参数；不采用 jku/x5u 或私钥材料。
                    keys[key_id] = {key: value[key] for key in ("kty", "n", "e")}
                if not keys:
                    raise ValueError("no signing keys")
            except (KeyError, TypeError, ValueError, AttributeError):
                raise HTTPException(503, "身份服务密钥格式无效") from None
            self._keys, self._expires = keys, time.monotonic() + self.config.delegated_jwks_cache_seconds
            if kid not in keys:
                raise unauthorized()
            return keys[kid]

    async def verify(self, token: str, required_scope="resume.read") -> VerifiedExternalIdentity:
        if not self.config.delegated_auth_enabled:
            raise HTTPException(404, "受托身份入口未启用")
        if len(token) > 16384:
            raise unauthorized()
        try:
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            if header.get("alg") != "RS256" or not isinstance(kid, str) or not 1 <= len(kid) <= 128:
                raise unauthorized()
        except (JWTError, TypeError, ValueError):
            raise unauthorized() from None
        async with httpx.AsyncClient(timeout=self.config.delegated_timeout_seconds, follow_redirects=False, trust_env=False) as client:
            key = await self._key(client, kid)
            try:
                payload = jwt.decode(token, key, algorithms=["RS256"], audience=self.config.delegated_audience,
                                     issuer=self.config.delegated_issuer,
                                     options={"require_sub": True, "require_iss": True, "require_aud": True, "require_exp": True, "require_iat": True})
                subject, session = payload["sub"], payload.get("sid")
                if not isinstance(subject, str) or not subject.strip() or len(subject.encode()) > 255:
                    raise unauthorized()
                if not isinstance(session, str) or not session or payload.get("typ") != "Bearer":
                    raise unauthorized()
                if type(payload["exp"]) is not int or type(payload["iat"]) is not int or payload["iat"] > time.time() + 5:
                    raise unauthorized()
                if not 0 < payload["exp"] - payload["iat"] <= self.config.delegated_max_lifetime_seconds:
                    raise unauthorized()
                actor = self.config.delegated_actor_clients.get(payload.get("azp"))
                username = payload.get("preferred_username")
                if actor is None or not isinstance(username, str) or not username or username.startswith("service-account-"):
                    raise unauthorized()
                if not isinstance(payload.get("scope"), str):
                    raise unauthorized()
                scopes = frozenset(payload["scope"].split())
            except (JWTError, KeyError, TypeError, ValueError, OverflowError):
                raise unauthorized() from None
            if required_scope not in scopes:
                raise HTTPException(403, "受托令牌缺少所需权限")
            status = await self._json(client, "POST", self.config.delegated_introspection_url,
                                      data={"token": token, "token_type_hint": "access_token"},
                                      auth=httpx.BasicAuth(self.config.delegated_client_id, self.config.delegated_client_secret.get_secret_value()))
            if status.get("active") is not True or status.get("sub") != subject:
                raise unauthorized()
            # 此绑定要求用户会话 sid；服务账号凭据不能替代用户会话。
            if status.get("sid") != session or status.get("username") != username:
                raise unauthorized()
            # 网络核验期间也可能到期，持久化身份前再次检查。
            if payload["exp"] <= time.time():
                raise unauthorized()
            return VerifiedExternalIdentity(payload["iss"], subject, actor, scopes)
