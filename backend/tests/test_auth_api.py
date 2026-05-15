"""认证 API 测试:注册、登录、me、双模认证。"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def auth_client() -> TestClient:
    """独立 TestClient——不带默认 X-User-Name header,模拟真实前端。"""
    with TestClient(app) as c:
        yield c


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

    def test_register_upgrades_dev_user(self, auth_client: TestClient):
        """dev 模式下已自动创建的无密码用户,注册时应升级而非报重复。"""
        username = _unique_username()
        # 先用 X-User-Name 触发自动创建
        auth_client.get("/api/v1/resumes", headers={"X-User-Name": username})
        # 再注册同名用户
        resp = auth_client.post("/api/auth/register", json={
            "username": username,
            "password": "upgrade123",
        })
        assert resp.status_code == 201
        assert resp.json()["user"]["username"] == username


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
