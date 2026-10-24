"""短事务裁决旧账号绑定；网络与 bcrypt 校验均在数据库锁外执行。"""
import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
import secrets

from fastapi import HTTPException
from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.core.binding_security import check_password, challenge_secret, digest
from app.models.external_binding import ExternalBindingAttempt, ExternalBindingAudit, ExternalBindingChallenge
from app.models.external_identity import ExternalIdentity
from app.models.user import User


def constraint_name(error):
    return getattr(getattr(error.orig, "__cause__", None), "constraint_name", None)


@asynccontextmanager
async def short_transaction(factory):
    try:
        async with asyncio.timeout(5):
            async with factory() as db, db.begin():
                await db.execute(text("SET LOCAL lock_timeout = '3s'"))
                await db.execute(text("SET LOCAL statement_timeout = '5s'"))
                yield db
    except TimeoutError:
        raise HTTPException(503, "绑定服务暂不可用") from None
    except DBAPIError as error:
        # 约束错误和代码错误不能被误报为可重试的外部服务错误。
        code = getattr(error.orig, "sqlstate", None)
        if not isinstance(error, IntegrityError) and (error.connection_invalidated or code in {"55P03", "57014", "40P01", "40001", "08000", "08003", "08006", "57P01"}):
            raise HTTPException(503, "绑定服务暂不可用") from None
        raise


async def database_now(db):
    # clock_timestamp 反映锁等待后的真实时间，不能使用事务开始时间代替。
    return (await db.execute(select(func.clock_timestamp()))).scalar_one()


async def locked_user(db, user_id):
    user = (await db.execute(select(User).where(User.id == user_id).with_for_update())).scalar_one_or_none()
    if user is None:
        raise HTTPException(401, "绑定认证失败")
    if not user.is_active:
        raise HTTPException(403, "账号已被禁用")
    return user


def require_live(credential, identity, now):
    if credential.expires_at <= now.timestamp() or identity.expires_at <= now.timestamp():
        raise HTTPException(401, "绑定认证失败")


async def reserve_binding_attempt(factory, credential, kind):
    """先提交限流槽位；后续业务失败不会恢复猜测密码的额度。"""
    async with short_transaction(factory) as db:
        user = await locked_user(db, credential.user_id)
        now = await database_now(db)
        if credential.expires_at <= now.timestamp():
            raise HTTPException(401, "绑定认证失败")
        times = (await db.execute(select(ExternalBindingAttempt.created_at).where(
            ExternalBindingAttempt.local_user_id == user.id, ExternalBindingAttempt.kind == kind,
            ExternalBindingAttempt.created_at > now-timedelta(minutes=5),
        ).order_by(ExternalBindingAttempt.created_at))).scalars().all()
        limit = {"create": 5, "confirm": 10}[kind]
        if len(times) >= limit:
            retry = max(1, int((times[-limit]+timedelta(minutes=5)-now).total_seconds())+1)
            raise HTTPException(429, "绑定尝试过于频繁", headers={"Retry-After": str(retry)})
        db.add(ExternalBindingAttempt(local_user_id=user.id, kind=kind, created_at=now))
        return user.hashed_password


async def prepare_binding(factory, credential, external_token, password, verifier, kind):
    snapshot = await reserve_binding_attempt(factory, credential, kind)
    identity = await verifier.verify(external_token, required_scope="identity.bind")
    config = verifier.config
    if identity.actor != "platform" or identity.client_id not in config.external_binding_allowed_clients:
        raise HTTPException(403, "调用方无绑定权限")
    await check_password(password, snapshot)
    return identity, snapshot


async def mappings_for(db, identity, user_id):
    rows = (await db.execute(select(ExternalIdentity).where(
        ExternalIdentity.issuer == identity.issuer,
        or_(ExternalIdentity.subject == identity.subject, ExternalIdentity.user_id == user_id),
    ))).scalars().all()
    same = next((row for row in rows if row.subject == identity.subject and row.user_id == user_id), None)
    return same, any(row is not same for row in rows)


async def validate_locked_user(db, credential, identity, snapshot):
    user = await locked_user(db, credential.user_id)
    if snapshot is None or user.hashed_password != snapshot:
        raise HTTPException(401, "账号认证状态已变化，请重试")
    require_live(credential, identity, await database_now(db))
    return user


async def create_binding_challenge(factory, credential, identity, snapshot):
    secret = challenge_secret()
    async with short_transaction(factory) as db:
        user = await validate_locked_user(db, credential, identity, snapshot)
        _, conflict = await mappings_for(db, identity, user.id)
        if conflict:
            raise HTTPException(409, "身份绑定冲突")
        now = await database_now(db)
        challenge = ExternalBindingChallenge(local_user_id=user.id, issuer=identity.issuer,
            subject=identity.subject, client_id=identity.client_id, session_id=identity.session_id,
            local_token_digest=credential.token_digest, secret_digest=digest(secret),
            created_at=now, expires_at=now+timedelta(minutes=5), status="pending")
        db.add(challenge)
        await db.flush()
        result = dict(challenge_id=challenge.id, challenge_secret=secret, expires_at=challenge.expires_at,
            user_id=user.id, username=user.username, issuer=identity.issuer, subject=identity.subject)
        require_live(credential, identity, await database_now(db))
    return result


def receipt(mapping, audit):
    return dict(status="bound", binding_id=mapping.id, user_id=mapping.user_id,
        issuer=mapping.issuer, subject=mapping.subject, audit_id=audit.id)


async def confirm_external_binding(factory, credential, identity, snapshot, challenge_id, secret):
    result = None
    async with short_transaction(factory) as db:
        user = await validate_locked_user(db, credential, identity, snapshot)
        challenge = (await db.execute(select(ExternalBindingChallenge).where(
            ExternalBindingChallenge.id == challenge_id).with_for_update())).scalar_one_or_none()
        if challenge is None or (challenge.local_user_id, challenge.issuer, challenge.subject, challenge.client_id, challenge.session_id) != (
            user.id, identity.issuer, identity.subject, identity.client_id, identity.session_id
        ) or not secrets.compare_digest(challenge.secret_digest, digest(secret)) or not secrets.compare_digest(challenge.local_token_digest, credential.token_digest):
            raise HTTPException(404, "绑定挑战不存在")
        now = await database_now(db)
        if challenge.expires_at <= now:
            raise HTTPException(410, "绑定挑战已过期")
        if challenge.status == "conflict":
            raise HTTPException(409, "身份绑定冲突")
        mapping, conflict = await mappings_for(db, identity, user.id)
        if challenge.status == "succeeded":
            if conflict or mapping is None or mapping.id != challenge.mapping_id:
                raise HTTPException(409, "身份绑定状态已变化")
            audit = (await db.execute(select(ExternalBindingAudit).where(ExternalBindingAudit.challenge_id == challenge.id))).scalar_one()
            result = receipt(mapping, audit)
        else:
            action = "already_bound"
            if not conflict and mapping is None:
                try:
                    async with db.begin_nested():
                        mapping = ExternalIdentity(issuer=identity.issuer, subject=identity.subject, user_id=user.id)
                        db.add(mapping)
                        await db.flush()
                    action = "bind"
                except IntegrityError as error:
                    if constraint_name(error) not in {"uq_external_identity_issuer_subject", "uq_external_identity_issuer_user"}:
                        raise
                    mapping, conflict = await mappings_for(db, identity, user.id)
                    if mapping is None:
                        conflict = True
            if conflict:
                # 先提交冲突终态，再在事务外生成 HTTP 错误。
                challenge.status = "conflict"
            else:
                challenge.status, challenge.mapping_id = "succeeded", mapping.id
                audit = ExternalBindingAudit(challenge_id=challenge.id, mapping_id=mapping.id,
                    local_user_id=user.id, issuer=identity.issuer, subject=identity.subject,
                    client_id=identity.client_id, action=action)
                db.add(audit)
                await db.flush()
                result = receipt(mapping, audit)
        now = await database_now(db)
        require_live(credential, identity, now)
        if challenge.expires_at <= now:
            raise HTTPException(410, "绑定挑战已过期")
    if result is None:
        raise HTTPException(409, "身份绑定冲突")
    return result
