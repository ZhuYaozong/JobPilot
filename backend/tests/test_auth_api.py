"""认证 API 测试:注册、登录、me、双模认证。"""

from collections.abc import Iterator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def auth_client(client: TestClient) -> Iterator[TestClient]:
    """复用 conftest 的全局 client,但临时移除默认的 X-User-Name header
    (模拟真实前端不带该 header 的情况)。

    起单独的 TestClient 会创建第二条 asyncpg 事件循环,
    跟全局 client 持有的连接池冲突,导致 "Future attached to a different loop"。
    """
    original = client.headers.pop("X-User-Name", None)
    try:
        yield client
    finally:
        if original is not None:
            client.headers["X-User-Name"] = original


def _unique_username() -> str:
    return f"authtest-{uuid4().hex[:12]}"


class TestRegister:
    """注册端点。"""

    def test_register_success(self, auth_client: TestClient):
        username = _unique_username()
        resp = auth_client.post("/api/auth/register", json={
            "username": username,
            "password": "test123456",
            "display_name": "测试用户",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["access_token"]
        assert data["token_type"] == "bearer"
        assert data["user"]["username"] == username
        assert data["user"]["display_name"] == "测试用户"

    def test_register_with_email(self, auth_client: TestClient):
        username = _unique_username()
        email = f"{username}@example.com"
        resp = auth_client.post("/api/auth/register", json={
            "username": username,
            "password": "test123456",
            "email": email,
        })
        assert resp.status_code == 201
        assert resp.json()["user"]["email"] == email

    def test_register_duplicate_username(self, auth_client: TestClient):
        username = _unique_username()
        auth_client.post("/api/auth/register", json={
            "username": username,
            "password": "test123456",
        })
        resp = auth_client.post("/api/auth/register", json={
            "username": username,
            "password": "other123456",
        })
        assert resp.status_code == 409

    def test_register_short_password(self, auth_client: TestClient):
        resp = auth_client.post("/api/auth/register", json={
            "username": _unique_username(),
            "password": "123",
        })
        assert resp.status_code == 422

    def test_register_cannot_claim_dev_user(self, auth_client: TestClient):
        """无密码账号仍有归属，注册不得直接认领。"""
        username = _unique_username()
        # 先用 X-User-Name 触发自动创建
        auth_client.get("/api/v1/resumes", headers={"X-User-Name": username})
        # 再注册同名用户
        resp = auth_client.post("/api/auth/register", json={
            "username": username,
            "password": "upgrade123",
        })
        assert resp.status_code == 409
        login = auth_client.post("/api/auth/login", json={"username": username, "password": "upgrade123"})
        assert login.status_code == 401


class TestLogin:
    """登录端点。"""

    def test_login_success(self, auth_client: TestClient):
        username = _unique_username()
        auth_client.post("/api/auth/register", json={
            "username": username,
            "password": "mypass789",
        })
        resp = auth_client.post("/api/auth/login", json={
            "username": username,
            "password": "mypass789",
        })
        assert resp.status_code == 200
        assert resp.json()["access_token"]

    def test_login_wrong_password(self, auth_client: TestClient):
        username = _unique_username()
        auth_client.post("/api/auth/register", json={
            "username": username,
            "password": "correct123",
        })
        resp = auth_client.post("/api/auth/login", json={
            "username": username,
            "password": "wrong123",
        })
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, auth_client: TestClient):
        resp = auth_client.post("/api/auth/login", json={
            "username": "nosuchuser99999",
            "password": "whatever",
        })
        assert resp.status_code == 401

    def test_login_dev_user_without_password(self, auth_client: TestClient):
        """dev 模式自动创建的用户没密码,登录应失败。"""
        username = _unique_username()
        auth_client.get("/api/v1/resumes", headers={"X-User-Name": username})
        resp = auth_client.post("/api/auth/login", json={
            "username": username,
            "password": "anything",
        })
        assert resp.status_code == 401


class TestMe:
    """me 端点 + JWT 认证。"""

    def test_me_with_token(self, auth_client: TestClient):
        username = _unique_username()
        reg_resp = auth_client.post("/api/auth/register", json={
            "username": username,
            "password": "metest123",
        })
        token = reg_resp.json()["access_token"]
        resp = auth_client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["username"] == username

    def test_me_with_invalid_token(self, auth_client: TestClient):
        resp = auth_client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert resp.status_code == 401

    def test_jwt_auth_on_regular_endpoint(self, auth_client: TestClient):
        """JWT token 可以访问普通受保护端点(如 resumes list)。"""
        username = _unique_username()
        reg_resp = auth_client.post("/api/auth/register", json={
            "username": username,
            "password": "apitest123",
        })
        token = reg_resp.json()["access_token"]
        resp = auth_client.get(
            "/api/v1/resumes",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200


class TestDevModeCompat:
    """dev 模式兼容:X-User-Name header 继续可用。"""

    def test_x_user_name_still_works(self, auth_client: TestClient):
        username = _unique_username()
        resp = auth_client.get(
            "/api/v1/resumes",
            headers={"X-User-Name": username},
        )
        assert resp.status_code == 200

    def test_jwt_takes_priority_over_header(self, auth_client: TestClient):
        """同时提供 JWT 和 X-User-Name 时,JWT 优先。"""
        jwt_user = _unique_username()
        header_user = _unique_username()
        reg_resp = auth_client.post("/api/auth/register", json={
            "username": jwt_user,
            "password": "priority123",
        })
        token = reg_resp.json()["access_token"]
        resp = auth_client.get(
            "/api/auth/me",
            headers={
                "Authorization": f"Bearer {token}",
                "X-User-Name": header_user,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["username"] == jwt_user


class TestAuthBoundary:
    """真实 API 与隔离数据库验证认证旁路被阻断。"""

    @pytest.mark.parametrize("headers", [{}, {"X-User-Name": ""}, {"X-User-Name": "   "}])
    def test_no_implicit_demo_identity(self, auth_client, headers):
        assert auth_client.get("/api/auth/me", headers=headers).status_code == 401

    @pytest.mark.parametrize("authorization", ["", "Basic ignored", "Token ignored", "Bearer", "Bearer ", "Bearer invalid", "Bearer bad token"])
    def test_bad_authorization_never_falls_back(self, auth_client, authorization):
        result = auth_client.get("/api/auth/me", headers={"Authorization": authorization, "X-User-Name": _unique_username()})
        assert result.status_code == 401

    def test_service_mode_rejects_dev_header(self, auth_client, monkeypatch):
        from app.core.config import settings
        monkeypatch.setattr(settings, "auth_dev_mode", False)
        assert auth_client.get("/api/auth/me", headers={"X-User-Name": _unique_username()}).status_code == 401

    def test_runtime_environment_cannot_allow_dev_header(self, auth_client, monkeypatch):
        from app.core.config import settings
        monkeypatch.setattr(settings, "app_env", "production")
        assert auth_client.get("/api/auth/me", headers={"X-User-Name": _unique_username()}).status_code == 401

    def test_password_account_cannot_use_dev_header(self, auth_client):
        name = _unique_username()
        registration = auth_client.post("/api/auth/register", json={"username": name, "password": "account-password"})
        assert registration.status_code == 201
        assert auth_client.get("/api/auth/me", headers={"X-User-Name": name}).status_code == 401
        assert auth_client.get("/api/auth/me", headers={"Authorization": "bearer " + registration.json()["access_token"]}).status_code == 200

    @pytest.mark.parametrize("has_password", [False, True])
    def test_disabled_user_cannot_be_claimed_or_reactivated(self, auth_client, auth_user_record, has_password):
        from app.core.security import hash_password, create_access_token
        name = _unique_username()
        user = auth_user_record(name, is_active=False, hashed_password=hash_password("original-password") if has_password else None)
        before = auth_user_record(name)
        assert auth_client.get("/api/auth/me", headers={"X-User-Name": name}).status_code == 403
        assert auth_client.post("/api/auth/register", json={"username": name, "password": "attacker-password", "email": "attacker@example.invalid", "display_name": "Changed"}).status_code == 409
        assert auth_user_record(name) == before
        token = create_access_token(user["id"], name)
        assert auth_client.get("/api/auth/me", headers={"Authorization": "Bearer " + token}).status_code == 403

    def test_legacy_account_data_not_transferred_by_registration(self, auth_client, auth_user_record):
        name = _unique_username()
        headers = {"X-User-Name": name}
        created = auth_client.post("/api/v1/resumes", headers=headers, json={"title": "Private resume", "raw_text": "Private content", "content_hash": _unique_username(), "source_type": "manual"})
        assert created.status_code == 201
        resume_id = created.json()["id"]
        before = auth_user_record(name)
        assert auth_client.post("/api/auth/register", json={"username": name, "password": "claim-password", "display_name": "Claimed", "email": "claim@example.invalid"}).status_code == 409
        assert auth_user_record(name) == before
        other = auth_client.post("/api/auth/register", json={"username": _unique_username(), "password": "other-password"})
        assert other.status_code == 201
        result = auth_client.get(f"/api/v1/resumes/{resume_id}", headers={"Authorization": "Bearer " + other.json()["access_token"]})
        assert result.status_code == 404
        assert auth_client.get(f"/api/v1/resumes/{resume_id}", headers=headers).status_code == 200

    @pytest.mark.parametrize("claims", [
        {}, {"sub": "1"}, {"exp": "future"}, {"sub": "1", "exp": None},
        {"sub": "1", "exp": True}, {"sub": "1", "exp": 1},
        *({"sub": value, "exp": 4102444800} for value in ("bad", "-1", "0", "01", "1.0", "1e2", "999999999999999999999", "2147483648", " 1", 1, [], {})),
    ])
    def test_invalid_signed_claims_are_unauthorized(self, auth_client, claims):
        from jose import jwt
        from app.core.config import settings
        token = jwt.encode(claims, settings.auth_secret_key, algorithm=settings.auth_algorithm)
        assert auth_client.get("/api/auth/me", headers={"Authorization": "Bearer " + token, "X-User-Name": _unique_username()}).status_code == 401

    def test_unknown_user_token_is_unauthorized(self, auth_client):
        from app.core.security import create_access_token
        token = create_access_token(2147483647, "missing")
        assert auth_client.get("/api/auth/me", headers={"Authorization": "Bearer " + token}).status_code == 401
