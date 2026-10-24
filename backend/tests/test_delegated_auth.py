"""受托令牌独立入口：签名/JWKS 为真实运算，身份源 HTTP 为受控替身。"""
import asyncio
from copy import deepcopy
import time

import httpx
import pytest


def test_disabled_by_default(client):
    assert client.get("/api/internal/v1/identity/me").status_code == 404


def test_valid_external_identity(client, delegated_idp):
    result = delegated_idp.get(client)
    assert result.status_code == 200
    data = result.json()
    assert data["subject"] == delegated_idp.subject
    assert data["actor"] == "tiki"
    assert data["user"]["username"].startswith("ext_")
    assert "resume.read" in data["scopes"]
    assert delegated_idp.seen_client_auth
    assert "hashed_password" not in data["user"]


@pytest.mark.parametrize("headers", [{}, {"X-User-Name": "demo"}, {"Authorization": "Basic ignored"}, {"Authorization": "Bearer "}])
def test_no_delegated_fallback(client, delegated_idp, headers):
    assert client.get("/api/internal/v1/identity/me", headers=headers).status_code == 401
    assert delegated_idp.jwks_route.call_count == 0


@pytest.mark.parametrize("changes", [
    {"iss": "https://wrong.invalid"}, {"aud": "tiki"}, {"azp": "stranger"}, {"azp": "jobpilot"},
    {"exp": 1}, {"nbf": 4102444800}, {"iat": 4102444800, "exp": 4102444980},
    {"sub": ""}, {"sub": "x" * 256}, {"sub": []}, {"sid": ""}, {"sid": None},
    {"typ": "ID"}, {"preferred_username": "service-account-tiki"},
    {"exp": None}, {"exp": True}, {"iat": True}, {"exp": 4102444800}, {"scope": []},
])
def test_invalid_claims_fail_before_introspection(client, delegated_idp, changes):
    result = delegated_idp.get(client, delegated_idp.token(**changes))
    assert result.status_code == 401
    assert delegated_idp.introspection_route.call_count == 0


@pytest.mark.parametrize("field", ["iss", "sub", "aud", "exp", "iat", "azp", "sid", "preferred_username"])
def test_required_claim_missing(client, delegated_idp, field):
    assert delegated_idp.get(client, delegated_idp.token(remove=(field,))).status_code == 401


def test_scope_checked(client, delegated_idp):
    assert delegated_idp.get(client, delegated_idp.token(scope="openid resume.write")).status_code == 403
    assert delegated_idp.introspection_route.call_count == 0


def test_wrong_signature_and_algorithm(client, delegated_idp, delegated_signing_keys):
    from jose import jwt
    claims = jwt.get_unverified_claims(delegated_idp.token())
    wrong = jwt.encode(claims, delegated_signing_keys["rotated"][0], algorithm="RS256", headers={"kid": "original"})
    assert delegated_idp.get(client, wrong).status_code == 401
    symmetric = jwt.encode(claims, "not-a-key", algorithm="HS256", headers={"kid": "original"})
    assert delegated_idp.get(client, symmetric).status_code == 401
    assert delegated_idp.introspection_route.call_count == 0


@pytest.mark.parametrize("status", [{"active": False}, {"active": "true"}, {"sub": "different-user"}, {"sid": "different-session"}, {"username": "different-name"}, {"username": "service-account-tiki"}])
def test_online_inactive_or_mismatch(client, delegated_idp, status):
    delegated_idp.status = status
    assert delegated_idp.get(client).status_code == 401


def test_disable_after_first_request_not_cached(client, delegated_idp):
    token = delegated_idp.token()
    assert delegated_idp.get(client, token).status_code == 200
    delegated_idp.status = {"active": False}
    assert delegated_idp.get(client, token).status_code == 401
    assert delegated_idp.introspection_route.call_count == 2
    assert delegated_idp.jwks_route.call_count == 1


@pytest.mark.parametrize("endpoint", ["jwks_route", "introspection_route"])
@pytest.mark.parametrize("failure", ["timeout", "server", "json", "list", "oversize", "redirect"])
def test_identity_service_failure_denies(client, delegated_idp, endpoint, failure):
    route = getattr(delegated_idp, endpoint)
    responses = {"server": httpx.Response(500), "json": httpx.Response(200, content=b"invalid"),
                 "list": httpx.Response(200, json=[]), "oversize": httpx.Response(200, content=b"x"*131073),
                 "redirect": httpx.Response(302, headers={"location": "https://attacker.invalid"})}
    if failure == "timeout":
        route.mock(side_effect=httpx.ReadTimeout("injected"))
    else:
        route.mock(return_value=responses[failure])
    response = delegated_idp.get(client)
    assert response.status_code == 503
    assert "token" not in response.text
    assert "test-only-introspection-secret" not in response.text


def test_unknown_kid_refresh_and_rotation(client, delegated_idp, delegated_signing_keys):
    assert delegated_idp.get(client).status_code == 200
    delegated_idp.keys.append(deepcopy(delegated_signing_keys["rotated"][1]))
    assert delegated_idp.get(client, delegated_idp.token(kid="rotated")).status_code == 200
    assert delegated_idp.get(client, delegated_idp.token()).status_code == 200
    assert delegated_idp.jwks_route.call_count == 2


def test_unknown_kid_refresh_is_bounded(client, delegated_idp, delegated_signing_keys):
    assert delegated_idp.get(client).status_code == 200
    unknown = delegated_idp.token(kid="rotated")
    assert delegated_idp.get(client, unknown).status_code == 401
    assert delegated_idp.get(client, unknown).status_code == 401
    assert delegated_idp.jwks_route.call_count == 2


def test_expired_jwks_cache_cannot_fail_open(client, delegated_idp):
    assert delegated_idp.get(client).status_code == 200
    delegated_idp.verifier._expires = 0
    delegated_idp.jwks_route.mock(return_value=httpx.Response(500))
    assert delegated_idp.get(client).status_code == 503


def test_token_url_header_not_used(client, delegated_idp, delegated_signing_keys):
    from jose import jwt
    claims = jwt.get_unverified_claims(delegated_idp.token())
    token = jwt.encode(claims, delegated_signing_keys["original"][0], algorithm="RS256",
                       headers={"kid": "original", "jku": "https://attacker.invalid/jwks", "x5u": "https://attacker.invalid/cert"})
    assert delegated_idp.get(client, token).status_code == 200
    assert delegated_idp.jwks_route.call_count == 1


@pytest.mark.parametrize("shape", [{}, {"keys": []}, {"keys": ["bad"]}, {"keys": [{"kid": "original", "kty": "RSA", "n": "AA", "e": "AQAB"}]}])
def test_invalid_jwks_denies(client, delegated_idp, shape):
    delegated_idp.jwks_route.mock(return_value=httpx.Response(200, json=shape))
    assert delegated_idp.get(client).status_code == 503


def test_token_expiring_during_online_check(client, delegated_idp, monkeypatch):
    now = int(time.time())
    original = delegated_idp.introspection
    def delayed(request):
        result = original(request)
        # 只替换验证模块使用的时间对象，避免影响整个测试进程的时钟。
        from types import SimpleNamespace
        import app.core.delegated_security as module
        monkeypatch.setattr(module, "time", SimpleNamespace(time=lambda: now+181, monotonic=time.monotonic))
        return result
    delegated_idp.introspection_route.mock(side_effect=delayed)
    assert delegated_idp.get(client, delegated_idp.token(iat=now, exp=now+180)).status_code == 401


def delegated_settings(**overrides):
    from app.core.config import Settings
    args = dict(_env_file=None, app_env="test", delegated_auth_enabled=True,
                delegated_issuer="https://identity.invalid/realm", delegated_jwks_url="https://identity.invalid/realm/keys",
                delegated_introspection_url="https://identity.invalid/realm/introspect", delegated_client_secret="j01b-unique-introspection-secret")
    args.update(overrides)
    return Settings(**args)


@pytest.mark.parametrize("changes", [
    {"delegated_issuer": ""}, {"delegated_jwks_url": "http://identity.invalid/realm/keys"},
    {"delegated_introspection_url": "https://attacker.invalid/realm/introspect"},
    {"delegated_jwks_url": "https://identity.invalid/other/keys"},
    {"delegated_jwks_url": "https://user:password@identity.invalid/realm/keys"},
    {"delegated_jwks_url": "https://identity.invalid/realm/keys?redirect=1"},
    {"delegated_jwks_url": "https://identity.invalid/realm/keys#fragment"},
    {"delegated_client_secret": ""}, {"delegated_client_id": " "}, {"delegated_audience": ""},
    {"delegated_actor_clients": {}}, {"delegated_actor_clients": {"": "tiki"}},
    {"delegated_actor_clients": {"caller": "admin"}}, {"delegated_jwks_cache_seconds": 3600},
    {"delegated_timeout_seconds": 60},
])
def test_invalid_delegated_configuration(changes, monkeypatch):
    from pydantic import ValidationError
    monkeypatch.delenv("DELEGATED_ACTOR_CLIENTS", raising=False)
    with pytest.raises(ValidationError):
        delegated_settings(**changes)


def test_valid_delegated_configuration_hides_secret():
    config = delegated_settings()
    assert "j01b-unique-introspection-secret" not in repr(config)
    assert config.delegated_audience == "jobpilot"
