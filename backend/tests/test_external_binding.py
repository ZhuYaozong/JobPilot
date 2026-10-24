"""通过真实签名、HTTP 替身和隔离数据库验收旧账号绑定。"""
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, update

from app.core.config import Settings
from app.core.security import create_access_token, hash_password
from app.models.external_binding import ExternalBindingAttempt, ExternalBindingAudit, ExternalBindingChallenge
from app.models.external_identity import ExternalIdentity
from conftest import _run_with_fresh_engine

PREFIX = "/api/auth/external-bindings"


@pytest.fixture
def binding_flow(client, delegated_idp, auth_user_record):
    provider = delegated_idp
    provider.config.delegated_actor_clients = {"tiki": "tiki", "binding-platform": "platform", "other-platform": "platform"}
    provider.config.external_binding_enabled = True
    provider.config.external_binding_allowed_clients = ["binding-platform"]

    class Flow:
        password = "legacy-binding-password"

        def __init__(self):
            self.user = auth_user_record("binding-"+uuid4().hex, hashed_password=hash_password(self.password))
            self.local = create_access_token(self.user["id"], self.user["username"])
            self.external = self.token()

        def token(self, **claims):
            return provider.token(azp="binding-platform", scope="identity.bind", **claims)

        def headers(self, **changes):
            headers = {"Authorization": "Bearer "+self.local, "X-External-Authorization": "Bearer "+self.external}
            headers.update(changes)
            return headers

        def create(self, **changes):
            body = {"password": self.password}
            body.update(changes)
            return client.post(PREFIX+"/challenges", json=body, headers=self.headers())

        def confirm(self, challenge, **changes):
            body = {key: challenge[key] for key in ("challenge_id", "challenge_secret")}
            body.update(password=self.password, confirm=True)
            body.update(changes)
            return client.post(PREFIX+"/confirm", json=body, headers=self.headers())

        def challenge(self):
            response = self.create()
            assert response.status_code == 201, response.text
            return response.json()

    return Flow()


def snapshot(user_id):
    result = {}
    async def work(db):
        for model, field in ((ExternalBindingChallenge, "local_user_id"), (ExternalBindingAudit, "local_user_id"), (ExternalBindingAttempt, "local_user_id"), (ExternalIdentity, "user_id")):
            result[model.__name__] = (await db.execute(select(func.count()).select_from(model).where(getattr(model, field) == user_id))).scalar_one()
    _run_with_fresh_engine(work)
    return result


def alter_challenge(challenge_id, **changes):
    async def work(db):
        await db.execute(update(ExternalBindingChallenge).where(ExternalBindingChallenge.id == UUID(challenge_id)).values(**changes))
        await db.commit()
    _run_with_fresh_engine(work)


def test_dual_proof_binds_legacy_resources_and_idempotent_receipt(client, binding_flow, delegated_idp):
    flow = binding_flow
    resume = client.post("/api/v1/resumes", headers={"Authorization": "Bearer "+flow.local}, json={"title": "Original", "raw_text": "Owned legacy data", "source_type": "manual", "content_hash": "binding-"+uuid4().hex})
    assert resume.status_code == 201
    challenge = flow.challenge()
    assert snapshot(flow.user["id"])["ExternalIdentity"] == 0
    first = flow.confirm(challenge)
    assert first.status_code == 200
    assert first.json() == flow.confirm(challenge).json()
    read = delegated_idp.get(client, delegated_idp.token())
    assert read.json()["user"]["id"] == flow.user["id"]
    own = client.get("/api/v1/resumes/"+str(resume.json()["id"]), headers={"Authorization": "Bearer "+flow.local})
    assert own.status_code == 200
    assert snapshot(flow.user["id"]) == {"ExternalIdentity": 1, "ExternalBindingAudit": 1, "ExternalBindingAttempt": 3, "ExternalBindingChallenge": 1}
    assert first.headers["Cache-Control"] == "no-store"


def test_same_binding_new_challenge_has_separate_audit(binding_flow):
    flow = binding_flow
    assert flow.confirm(flow.challenge()).status_code == 200
    assert flow.confirm(flow.challenge()).status_code == 200
    counts = snapshot(flow.user["id"])
    assert counts["ExternalIdentity"] == 1 and counts["ExternalBindingAudit"] == 2


@pytest.mark.parametrize("claims", [
    {"scope": "resume.read"}, {"azp": "tiki", "scope": "identity.bind"},
    {"azp": "other-platform"}, {"preferred_username": "service-account-platform"},
    {"iss": "https://forged.invalid"}, {"aud": "other"}, {"sid": ""},
])
def test_external_wrong_authority_denied(binding_flow, delegated_idp, claims):
    flow = binding_flow
    values = {"azp": "binding-platform", "scope": "identity.bind"}
    values.update(claims)
    flow.external = delegated_idp.token(**values)
    assert flow.create().status_code in {401, 403}
    assert snapshot(flow.user["id"])["ExternalIdentity"] == 0


def test_disabled_by_default(client, delegated_idp):
    response = client.post(PREFIX+"/challenges", json={"password": "secret"})
    assert response.status_code == 404


@pytest.mark.parametrize("mode", ["dev", "external-as-local", "missing-external", "mcp"])
def test_no_fallback_or_token_type_confusion(client, binding_flow, mode):
    flow = binding_flow
    headers = flow.headers()
    if mode == "dev":
        headers.pop("Authorization")
        headers["X-User-Name"] = flow.user["username"]
    elif mode == "external-as-local":
        headers["Authorization"] = "Bearer "+flow.external
    elif mode == "missing-external":
        headers.pop("X-External-Authorization")
    else:
        from app.core.security import create_mcp_access_token
        headers["Authorization"] = "Bearer "+create_mcp_access_token(flow.user["id"], flow.user["username"])
    assert client.post(PREFIX+"/challenges", json={"password": flow.password}, headers=headers).status_code == 401


def test_password_required_and_failed_attempts_persist(binding_flow):
    flow = binding_flow
    assert flow.create(password="incorrect").status_code == 401
    assert snapshot(flow.user["id"])["ExternalBindingAttempt"] == 1
    challenge = flow.challenge()
    assert flow.confirm(challenge, password="incorrect").status_code == 401
    assert snapshot(flow.user["id"])["ExternalIdentity"] == 0


@pytest.mark.parametrize("change", [{"hashed_password": None}, {"is_active": False}])
def test_unclaimable_or_disabled_user(binding_flow, auth_user_record, change):
    flow = binding_flow
    auth_user_record(flow.user["username"], **change)
    assert flow.create().status_code in {401, 403}


def test_jit_account_cannot_be_rebound(binding_flow, delegated_idp, client):
    flow = binding_flow
    existing = delegated_idp.get(client).json()["user"]["id"]
    assert existing != flow.user["id"]
    assert flow.create().status_code == 409
    assert snapshot(flow.user["id"])["ExternalIdentity"] == 0


def test_jit_after_challenge_marks_terminal_conflict(binding_flow, delegated_idp, client):
    flow = binding_flow
    challenge = flow.challenge()
    delegated_idp.get(client)
    assert flow.confirm(challenge).status_code == 409
    async def work(db):
        row = await db.get(ExternalBindingChallenge, UUID(challenge["challenge_id"]))
        assert row.status == "conflict"
    _run_with_fresh_engine(work)
    assert flow.confirm(challenge).status_code == 409


@pytest.mark.parametrize("mode", ["secret", "subject", "sid", "client", "local-token", "unknown"])
def test_challenge_cannot_cross_identity_or_session(binding_flow, delegated_idp, mode):
    flow = binding_flow
    challenge = flow.challenge()
    if mode == "secret":
        challenge["challenge_secret"] = "z"*43
    elif mode == "unknown":
        challenge["challenge_id"] = str(uuid4())
    elif mode == "subject":
        flow.external = flow.token(sub="other-subject")
    elif mode == "sid":
        flow.external = flow.token(sid="other-session")
    elif mode == "client":
        delegated_idp.config.external_binding_allowed_clients.append("other-platform")
        flow.external = delegated_idp.token(azp="other-platform", scope="identity.bind")
    else:
        from jose import jwt
        from app.core.config import settings
        from app.core.security import decode_access_token
        claims = decode_access_token(flow.local)
        claims["nonce"] = uuid4().hex
        flow.local = jwt.encode(claims, settings.auth_secret_key, algorithm="HS256")
    assert flow.confirm(challenge).status_code == 404


def test_same_external_session_can_refresh(binding_flow):
    import time
    flow = binding_flow
    challenge = flow.challenge()
    flow.external = flow.token(exp=int(time.time())+200)
    assert flow.confirm(challenge).status_code == 200


def test_expired_challenge_and_success_receipt_are_unusable(binding_flow):
    from datetime import datetime, timezone
    flow = binding_flow
    challenge = flow.challenge()
    assert flow.confirm(challenge).status_code == 200
    now = datetime.now(timezone.utc)
    alter_challenge(challenge["challenge_id"], created_at=now-timedelta(minutes=10), expires_at=now-timedelta(minutes=1))
    assert flow.confirm(challenge).status_code == 410


def test_creation_rate_limit_and_window_recovery(binding_flow):
    flow = binding_flow
    for _ in range(5):
        assert flow.create(password="wrong").status_code == 401
    response = flow.create()
    assert response.status_code == 429 and 1 <= int(response.headers["Retry-After"]) <= 301
    async def work(db):
        await db.execute(update(ExternalBindingAttempt).where(ExternalBindingAttempt.local_user_id == flow.user["id"]).values(created_at=func.now()-timedelta(minutes=6)))
        await db.commit()
    _run_with_fresh_engine(work)
    assert flow.create().status_code == 201


def test_confirmation_rate_limit(binding_flow):
    flow = binding_flow
    challenge = flow.challenge()
    for _ in range(10):
        assert flow.confirm(challenge, password="wrong").status_code == 401
    assert flow.confirm(challenge).status_code == 429


@pytest.mark.parametrize("changes", [{"password": []}, {"user_id": 123}, {"password": "x"*129}])
def test_sensitive_validation_never_echoes_input(binding_flow, changes, caplog):
    response = binding_flow.create(**changes)
    assert response.status_code == 422
    assert response.json() == {"detail": "绑定请求格式无效"}
    assert binding_flow.password not in response.text+caplog.text
    assert binding_flow.external not in response.text+caplog.text
    assert response.headers["Cache-Control"] == "no-store"


def test_confirmation_requires_true_and_password_byte_limit(binding_flow):
    flow = binding_flow
    challenge = flow.challenge()
    assert flow.confirm(challenge, confirm=False).status_code == 422
    assert flow.confirm(challenge, confirm=1).status_code == 422
    assert flow.create(password="密"*25).status_code == 401


@pytest.mark.parametrize("change", [
    {"external_binding_allowed_clients": []}, {"external_binding_allowed_clients": ["tiki"]},
    {"external_binding_allowed_clients": ["*"]}, {"external_binding_allowed_clients": ["platform", "platform"]},
    {"delegated_auth_enabled": False},
])
def test_binding_configuration_rejects_unsafe_settings(delegated_idp, change):
    from pydantic import ValidationError
    args = delegated_idp.config.model_dump()
    args.update(external_binding_enabled=True, delegated_actor_clients={"platform": "platform", "tiki": "tiki"}, external_binding_allowed_clients=["platform"])
    args.update(change)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **args)


def test_external_disabled_after_challenge_denies_confirmation(binding_flow, delegated_idp):
    flow = binding_flow
    challenge = flow.challenge()
    delegated_idp.status["active"] = False
    assert flow.confirm(challenge).status_code == 401
    assert snapshot(flow.user["id"])["ExternalIdentity"] == 0


@pytest.mark.parametrize("change", [{"is_active": False}, {"hashed_password": hash_password("new-password")}])
def test_account_changed_during_external_verification(binding_flow, delegated_idp, auth_user_record, change):
    flow = binding_flow
    challenge = flow.challenge()
    original = delegated_idp.introspection
    def during_check(request):
        # HTTP 替身运行在应用事件循环，线程包装隔离库修改以模拟外部并发管理操作。
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(auth_user_record, flow.user["username"], **change).result()
        return original(request)
    delegated_idp.introspection_route.mock(side_effect=during_check)
    assert flow.confirm(challenge).status_code in {401, 403}
    assert snapshot(flow.user["id"])["ExternalIdentity"] == 0


def test_same_issuer_second_subject_cannot_attach(binding_flow):
    flow = binding_flow
    assert flow.confirm(flow.challenge()).status_code == 200
    flow.external = flow.token(sub="new-"+uuid4().hex)
    assert flow.create().status_code == 409


def test_failure_response_does_not_expose_secrets(binding_flow, caplog):
    flow = binding_flow
    challenge = flow.challenge()
    response = flow.confirm(challenge, password="sensitive-wrong-password")
    combined = response.text+caplog.text
    for value in (flow.local, flow.external, challenge["challenge_secret"], "sensitive-wrong-password"):
        assert value not in combined
    assert response.headers["Cache-Control"] == "no-store"


def test_unknown_failure_is_500_and_never_logs_exception_credentials(binding_flow, monkeypatch, caplog):
    flow = binding_flow
    import app.api.external_bindings as route
    async def fail(*args, **kwargs):
        raise RuntimeError(flow.external+flow.password)
    monkeypatch.setattr(route, "create_binding_challenge", fail)
    response = flow.create()
    assert response.status_code == 500
    assert flow.external not in response.text+caplog.text
    assert flow.password not in response.text+caplog.text
    assert "RuntimeError" in caplog.text
    assert response.headers["Cache-Control"] == "no-store"
