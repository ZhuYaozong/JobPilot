"""独立连接强制制造绑定竞争，验证约束、回滚与跨实例限流。"""
import asyncio
from datetime import timedelta
from uuid import uuid4

from fastapi import HTTPException
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.binding_security import LocalBindingCredential
from app.core.config import settings
from app.core.delegated_security import VerifiedExternalIdentity
from app.models.external_binding import ExternalBindingAudit, ExternalBindingChallenge, ExternalBindingAttempt
from app.models.external_identity import ExternalIdentity
from app.models.user import User
import app.services.external_binding_service as service
from app.services.external_identity_service import resolve_external_user


async def setup_case(count=1):
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db, db.begin():
        users = [User(username="race-"+uuid4().hex, display_name="Owner", hashed_password="verified-snapshot", is_active=True) for _ in range(count)]
        db.add_all(users)
        await db.flush()
        now = await service.database_now(db)
    credentials = [LocalBindingCredential(user.id, "a"*64, (now+timedelta(minutes=10)).timestamp()) for user in users]
    identity = VerifiedExternalIdentity("https://identity.invalid/realm", uuid4().hex, "platform", frozenset({"identity.bind"}), "platform-client", "session", int((now+timedelta(minutes=10)).timestamp()))
    return engine, factory, users, credentials, identity


async def confirm(factory, credential, identity, challenge):
    return await service.confirm_external_binding(factory, credential, identity, "verified-snapshot", challenge["challenge_id"], challenge["challenge_secret"])


def test_same_challenge_concurrent_receipt_once():
    async def work():
        engine, factory, users, credentials, identity = await setup_case()
        try:
            c = await service.create_binding_challenge(factory, credentials[0], identity, "verified-snapshot")
            values = await asyncio.gather(*(confirm(factory, credentials[0], identity, c) for _ in range(3)))
            assert values[0] == values[1] == values[2]
            async with factory() as db:
                assert (await db.execute(select(func.count()).select_from(ExternalBindingAudit).where(ExternalBindingAudit.local_user_id == users[0].id))).scalar_one() == 1
        finally:
            await engine.dispose()
    asyncio.run(work())


def test_two_owners_race_one_identity(monkeypatch):
    async def work():
        engine, factory, users, credentials, identity = await setup_case(2)
        try:
            challenges = [await service.create_binding_challenge(factory, c, identity, "verified-snapshot") for c in credentials]
            barrier = asyncio.Barrier(2)
            original = service.mappings_for
            calls = 0
            async def synchronized(*args):
                nonlocal calls
                result = await original(*args)
                calls += 1
                if calls <= 2:
                    await asyncio.wait_for(barrier.wait(), 2)
                return result
            monkeypatch.setattr(service, "mappings_for", synchronized)
            values = await asyncio.gather(*(confirm(factory, c, identity, challenge) for c, challenge in zip(credentials, challenges)), return_exceptions=True)
            assert sum(isinstance(v, dict) for v in values) == 1
            assert sum(isinstance(v, HTTPException) and v.status_code == 409 for v in values) == 1
            async with factory() as db:
                rows = (await db.execute(select(ExternalIdentity).where(ExternalIdentity.subject == identity.subject))).scalars().all()
                assert len(rows) == 1
                states = (await db.execute(select(ExternalBindingChallenge.status).where(ExternalBindingChallenge.id.in_([c["challenge_id"] for c in challenges])))).scalars().all()
                assert sorted(states) == ["conflict", "succeeded"]
        finally:
            await engine.dispose()
    asyncio.run(work())


def test_two_subjects_race_same_owner():
    async def work():
        engine, factory, users, credentials, identity = await setup_case()
        from dataclasses import replace
        other = replace(identity, subject=uuid4().hex)
        try:
            challenges = [await service.create_binding_challenge(factory, credentials[0], i, "verified-snapshot") for i in (identity, other)]
            values = await asyncio.gather(*(confirm(factory, credentials[0], i, c) for i, c in zip((identity, other), challenges)), return_exceptions=True)
            assert sum(isinstance(v, dict) for v in values) == 1
            assert sum(isinstance(v, HTTPException) and v.status_code == 409 for v in values) == 1
        finally:
            await engine.dispose()
    asyncio.run(work())


@pytest.mark.parametrize("winner", ["binding", "jit"])
def test_jit_and_binding_unique_race_no_orphan(monkeypatch, winner):
    async def work():
        engine, factory, users, credentials, identity = await setup_case()
        try:
            challenge = await service.create_binding_challenge(factory, credentials[0], identity, "verified-snapshot")
            jit_read = asyncio.Event()
            binding_read = asyncio.Event()
            release = asyncio.Event()
            original = service.mappings_for

            async def binding_mapping(*args):
                result = await original(*args)
                if not binding_read.is_set():
                    binding_read.set()
                    await asyncio.wait_for(jit_read.wait(), 2)
                    if winner == "jit":
                        await asyncio.wait_for(release.wait(), 2)
                return result
            monkeypatch.setattr(service, "mappings_for", binding_mapping)

            class JitSession(AsyncSession):
                first = True
                async def execute(self, statement, *args, **kwargs):
                    result = await super().execute(statement, *args, **kwargs)
                    if self.first and "FROM external_identities" in str(statement):
                        self.first = False
                        jit_read.set()
                        await asyncio.wait_for(binding_read.wait(), 2)
                        if winner == "binding":
                            await asyncio.wait_for(release.wait(), 2)
                    return result

            async with factory() as db:
                before = (await db.execute(select(func.count()).select_from(User))).scalar_one()

            async def binding():
                try:
                    return await confirm(factory, credentials[0], identity, challenge)
                finally:
                    if winner == "binding":
                        release.set()
            async def jit():
                try:
                    async with JitSession(engine, expire_on_commit=False) as db:
                        return await resolve_external_user(db, identity)
                finally:
                    if winner == "jit":
                        release.set()
            values = await asyncio.gather(binding(), jit(), return_exceptions=True)
            if winner == "binding":
                assert values[0]["user_id"] == values[1].id == users[0].id
            else:
                assert isinstance(values[0], HTTPException) and values[0].status_code == 409
                assert values[1].id != users[0].id
            async with factory() as db:
                after = (await db.execute(select(func.count()).select_from(User))).scalar_one()
                assert after == before+(winner == "jit")
        finally:
            await engine.dispose()
    asyncio.run(work())


def test_cross_instance_attempt_limit():
    async def work():
        engine, factory, users, credentials, identity = await setup_case()
        engine2 = create_async_engine(settings.database_url, poolclass=NullPool)
        factory2 = async_sessionmaker(engine2, expire_on_commit=False)
        try:
            values = await asyncio.gather(*(service.reserve_binding_attempt(factory if i % 2 else factory2, credentials[0], "create") for i in range(8)), return_exceptions=True)
            assert sum(v == "verified-snapshot" for v in values) == 5
            assert sum(isinstance(v, HTTPException) and v.status_code == 429 for v in values) == 3
            async with factory() as db:
                assert (await db.execute(select(func.count()).select_from(ExternalBindingAttempt).where(ExternalBindingAttempt.local_user_id == users[0].id))).scalar_one() == 5
        finally:
            await engine.dispose()
            await engine2.dispose()
    asyncio.run(work())


def test_audit_failure_rolls_back_mapping_and_consumption():
    async def work():
        engine, factory, users, credentials, identity = await setup_case()
        try:
            await service.reserve_binding_attempt(factory, credentials[0], "confirm")
            c = await service.create_binding_challenge(factory, credentials[0], identity, "verified-snapshot")
            class FailingSession(AsyncSession):
                async def flush(self, *args, **kwargs):
                    if any(isinstance(row, ExternalBindingAudit) for row in self.new):
                        raise RuntimeError("injected-audit-failure")
                    return await super().flush(*args, **kwargs)
            broken = async_sessionmaker(engine, class_=FailingSession, expire_on_commit=False)
            with pytest.raises(RuntimeError, match="injected-audit-failure"):
                await confirm(broken, credentials[0], identity, c)
            async with factory() as db:
                assert (await db.get(ExternalBindingChallenge, c["challenge_id"])).status == "pending"
                assert (await db.execute(select(ExternalIdentity).where(ExternalIdentity.user_id == users[0].id))).scalar_one_or_none() is None
                assert (await db.execute(select(func.count()).select_from(ExternalBindingAttempt).where(ExternalBindingAttempt.local_user_id == users[0].id))).scalar_one() == 1
            assert (await confirm(factory, credentials[0], identity, c))["user_id"] == users[0].id
        finally:
            await engine.dispose()
    asyncio.run(work())


def test_lock_timeout_is_retryable_and_does_not_add_attempt():
    async def work():
        engine, factory, users, credentials, identity = await setup_case()
        try:
            async with factory() as blocker, blocker.begin():
                await service.locked_user(blocker, users[0].id)
                with pytest.raises(HTTPException) as error:
                    await service.reserve_binding_attempt(factory, credentials[0], "create")
                assert error.value.status_code == 503
            async with factory() as db:
                assert (await db.execute(select(func.count()).select_from(ExternalBindingAttempt).where(ExternalBindingAttempt.local_user_id == users[0].id))).scalar_one() == 0
        finally:
            await engine.dispose()
    asyncio.run(work())


def test_token_expiring_before_commit_rolls_back_audit_and_mapping(monkeypatch):
    async def work():
        engine, factory, users, credentials, identity = await setup_case()
        try:
            challenge = await service.create_binding_challenge(factory, credentials[0], identity, "verified-snapshot")
            original = service.database_now
            calls = 0
            async def advance_at_commit(db):
                nonlocal calls
                now = await original(db)
                calls += 1
                # 第一次是锁用户后验证，第二次是挑战验证，第三次在写入后提交前。
                return now+timedelta(minutes=11) if calls == 3 else now
            monkeypatch.setattr(service, "database_now", advance_at_commit)
            with pytest.raises(HTTPException) as error:
                await confirm(factory, credentials[0], identity, challenge)
            assert error.value.status_code == 401
            async with factory() as db:
                assert (await db.get(ExternalBindingChallenge, challenge["challenge_id"])).status == "pending"
                assert (await db.execute(select(ExternalIdentity).where(ExternalIdentity.user_id == users[0].id))).scalar_one_or_none() is None
                assert (await db.execute(select(ExternalBindingAudit).where(ExternalBindingAudit.local_user_id == users[0].id))).scalar_one_or_none() is None
        finally:
            await engine.dispose()
    asyncio.run(work())
