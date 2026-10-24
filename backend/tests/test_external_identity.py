"""真实隔离 PostgreSQL 验证外部身份映射与资源归属，不模拟唯一约束。"""
import asyncio
from uuid import uuid4

from fastapi import HTTPException
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.delegated_security import VerifiedExternalIdentity
from app.models.external_identity import ExternalIdentity
from app.models.resume import Resume
from app.models.user import User
from app.services.external_identity_service import resolve_external_user
from app.services.user_scope_service import get_resume_for_user_or_404


def test_same_identity_stable_and_subject_is_not_local_id(client, delegated_idp):
    first = delegated_idp.get(client).json()
    second = delegated_idp.get(client).json()
    assert first["user"]["id"] == second["user"]["id"]
    # 请求参数/身份头不能选择被映射的账号。
    result = client.get("/api/internal/v1/identity/me?user_id=1&principal_id=other", headers={"Authorization": "Bearer " + delegated_idp.token(), "X-User-Name": "other", "X-Principal-Id": "other"})
    assert result.status_code == 200
    assert result.json()["user"]["id"] == first["user"]["id"]


def test_same_display_name_email_cannot_claim_old_user(client, delegated_idp, auth_user_record):
    name = "legacy-" + uuid4().hex
    old = auth_user_record(name, email="mail-"+uuid4().hex+"@example.invalid")
    token = delegated_idp.token(preferred_username=name, email=old["email"])
    new = delegated_idp.get(client, token)
    assert new.status_code == 200
    assert new.json()["user"]["id"] != old["id"]
    assert new.json()["user"]["email"] is None
    assert auth_user_record(name) == old


def test_external_user_cannot_use_dev_head_or_local_login(client, delegated_idp):
    user = delegated_idp.get(client).json()["user"]
    assert client.get("/api/auth/me", headers={"X-User-Name": user["username"]}).status_code == 401
    assert client.post("/api/auth/login", json={"username": user["username"], "password": "anything"}).status_code == 401
    assert client.post("/api/auth/register", json={"username": user["username"], "password": "claim-password"}).status_code == 409


def test_local_disabled_user_refuses_external_identity(client, delegated_idp, auth_user_record):
    user = delegated_idp.get(client).json()["user"]
    auth_user_record(user["username"], is_active=False)
    assert delegated_idp.get(client).status_code == 403
    assert not auth_user_record(user["username"])["is_active"]


def test_external_token_not_accepted_on_legacy_api(client, delegated_idp):
    response = client.get("/api/v1/resumes", headers={"Authorization": "Bearer " + delegated_idp.token()})
    assert response.status_code == 401


def test_concurrent_creation_has_one_mapping_and_no_orphan():
    async def work():
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        barrier = asyncio.Barrier(2)
        class BarrierSession(AsyncSession):
            first = True
            async def execute(self, statement, *args, **kwargs):
                result = await super().execute(statement, *args, **kwargs)
                if self.first and "FROM external_identities" in str(statement):
                    self.first = False
                    # 两个独立事务均读到无映射后才继续，强制命中唯一竞争路径。
                    await asyncio.wait_for(barrier.wait(), timeout=10)
                return result
        factory = async_sessionmaker(engine, class_=BarrierSession, expire_on_commit=False)
        identity = VerifiedExternalIdentity("https://issuer.example.invalid", uuid4().hex, "tiki", frozenset({"resume.read"}))
        try:
            async with AsyncSession(engine) as db:
                before = (await db.execute(select(func.count()).select_from(User))).scalar_one()
            async def create():
                async with factory() as db:
                    return (await resolve_external_user(db, identity)).id
            ids = await asyncio.wait_for(asyncio.gather(create(), create()), timeout=20)
            assert ids[0] == ids[1]
            async with AsyncSession(engine) as db:
                after = (await db.execute(select(func.count()).select_from(User))).scalar_one()
                count = (await db.execute(select(func.count()).select_from(ExternalIdentity).where(ExternalIdentity.issuer == identity.issuer, ExternalIdentity.subject == identity.subject))).scalar_one()
            assert after == before + 1
            assert count == 1
        finally:
            await engine.dispose()
    asyncio.run(work())


def test_same_subject_different_issuer_and_two_users_resource_isolation():
    async def work():
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        subject = uuid4().hex
        try:
            async with factory() as db:
                alice = await resolve_external_user(db, VerifiedExternalIdentity("https://issuer-a.invalid", subject, "tiki", frozenset()))
            async with factory() as db:
                bob = await resolve_external_user(db, VerifiedExternalIdentity("https://issuer-b.invalid", subject, "tiki", frozenset()))
            assert alice.id != bob.id
            async with factory() as db:
                resume = Resume(user_id=alice.id, title="Private", raw_text="Only Alice", source_type="manual", content_hash=uuid4().hex)
                db.add(resume)
                await db.commit()
                assert (await get_resume_for_user_or_404(db, resume.id, alice)).id == resume.id
                with pytest.raises(HTTPException) as error:
                    await get_resume_for_user_or_404(db, resume.id, bob)
                assert error.value.status_code == 404
        finally:
            await engine.dispose()
    asyncio.run(work())


def test_failed_mapping_insert_rolls_back_new_user(monkeypatch):
    async def work():
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        identity = VerifiedExternalIdentity("https://issuer.invalid", uuid4().hex, "tiki", frozenset())
        try:
            async with AsyncSession(engine) as db:
                before = (await db.execute(select(func.count()).select_from(User))).scalar_one()
            async with AsyncSession(engine, expire_on_commit=False) as db:
                original = db.flush
                async def fail_mapping(*args, **kwargs):
                    if any(isinstance(obj, ExternalIdentity) for obj in db.new):
                        raise RuntimeError("injected-mapping-failure")
                    await original(*args, **kwargs)
                monkeypatch.setattr(db, "flush", fail_mapping)
                with pytest.raises(RuntimeError, match="injected"):
                    await resolve_external_user(db, identity)
            async with AsyncSession(engine) as db:
                assert (await db.execute(select(func.count()).select_from(User))).scalar_one() == before
        finally:
            await engine.dispose()
    asyncio.run(work())
