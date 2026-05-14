import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.core.config import settings
from app.db.base import Base
from app import models  # noqa: F401

# Alembic Config 对象，用于读取当前 .ini 文件里的配置值。
config = context.config

# 按配置文件初始化 Python 日志。
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", settings.database_url)
target_metadata = Base.metadata

# env.py 如果需要读取其他配置值，可以按下面的方式获取：
# my_important_option = config.get_main_option("my_important_option")
# 以此类推。


def run_migrations_offline() -> None:
    """以离线模式运行迁移。

    这里仅使用 URL 配置 Alembic context，不创建 Engine。
    离线模式下甚至不需要可用的 DBAPI。

    这里的 context.execute() 会把 SQL 字符串输出到迁移脚本输出流。

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """以在线模式运行迁移。

    在线模式需要创建 Engine，并把连接绑定到 Alembic context。

    """
    asyncio.run(run_async_migrations())


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
