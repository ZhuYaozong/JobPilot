"""临时 schema 内运行真实 revision；最终回滚，不触碰现存测试表。"""
import asyncio
import importlib.util
from pathlib import Path
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.models.user import User


def revision():
    path = Path(__file__).resolve().parents[1]/"alembic/versions/a41c98d72b60_add_external_binding.py"
    spec = importlib.util.spec_from_file_location("binding_revision", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def isolated_revision(check):
    async def work():
        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        try:
            async with engine.connect() as connection:
                transaction = await connection.begin()
                try:
                    def run(conn):
                        schema = "binding_test_"+uuid4().hex
                        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
                        conn.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                        User.__table__.create(conn)
                        conn.execute(text("CREATE TABLE external_identities (id serial PRIMARY KEY, issuer varchar(512) NOT NULL, subject varchar(255) NOT NULL, user_id integer NOT NULL REFERENCES users(id) ON DELETE RESTRICT, created_at timestamptz NOT NULL DEFAULT now(), CONSTRAINT uq_external_identity_issuer_subject UNIQUE(issuer,subject))"))
                        conn.execute(text("INSERT INTO users(username,display_name) VALUES ('old-owner','Original')"))
                        with Operations.context(MigrationContext.configure(conn)):
                            check(conn, revision())
                    await connection.run_sync(run)
                finally:
                    # 包括临时 schema、序列和数据在内全部回滚。
                    await transaction.rollback()
        finally:
            await engine.dispose()
    asyncio.run(work())


def test_empty_migration_roundtrip_keeps_legacy_user():
    def check(conn, migration):
        migration.upgrade()
        assert conn.execute(text("SELECT count(*) FROM users")).scalar_one() == 1
        migration.downgrade()
        assert conn.execute(text("SELECT to_regclass('external_binding_challenges')")).scalar_one() is None
        migration.upgrade()
        assert conn.execute(text("SELECT display_name FROM users")).scalar_one() == "Original"
    isolated_revision(check)


def test_duplicate_legacy_mappings_block_upgrade_without_rewriting():
    def check(conn, migration):
        conn.execute(text("INSERT INTO external_identities(issuer,subject,user_id) VALUES ('issuer','one',1),('issuer','two',1)"))
        with pytest.raises(RuntimeError, match="重复"):
            migration.upgrade()
        assert conn.execute(text("SELECT count(*) FROM external_identities")).scalar_one() == 2
        assert conn.execute(text("SELECT to_regclass('external_binding_attempts')")).scalar_one() is None
    isolated_revision(check)


@pytest.mark.parametrize("data", ["mapping", "attempt", "challenge", "audit"])
def test_nonempty_data_blocks_downgrade(data):
    def check(conn, migration):
        migration.upgrade()
        if data in {"mapping", "audit"}:
            conn.execute(text("INSERT INTO external_identities(issuer,subject,user_id) VALUES ('issuer','one',1)"))
        if data in {"challenge", "audit"}:
            conn.execute(text("INSERT INTO external_binding_challenges(id,local_user_id,issuer,subject,client_id,session_id,local_token_digest,secret_digest,expires_at,status) VALUES (:id,1,'issuer','one','platform','session',:digest,:digest,now()+interval '5 minutes','pending')"), {"id": uuid4(), "digest": "a"*64})
        if data == "audit":
            challenge = conn.execute(text("SELECT id FROM external_binding_challenges")).scalar_one()
            conn.execute(text("UPDATE external_binding_challenges SET status='succeeded',mapping_id=1"))
            conn.execute(text("INSERT INTO external_binding_audits(id,challenge_id,mapping_id,local_user_id,issuer,subject,client_id,action) VALUES (:id,:challenge,1,1,'issuer','one','platform','bind')"), {"id": uuid4(), "challenge": challenge})
        if data == "attempt":
            conn.execute(text("INSERT INTO external_binding_attempts(id,local_user_id,kind,request_id) VALUES (:id,1,'create',:request)"), {"id": uuid4(), "request": uuid4()})
        with pytest.raises(RuntimeError, match="非空"):
            migration.downgrade()
        assert conn.execute(text("SELECT to_regclass('external_binding_audits')")).scalar_one() is not None
        assert conn.execute(text("SELECT count(*) FROM users")).scalar_one() == 1
    isolated_revision(check)
