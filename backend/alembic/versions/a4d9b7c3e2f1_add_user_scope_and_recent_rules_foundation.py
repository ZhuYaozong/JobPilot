"""增加用户隔离基础

修订 ID: a4d9b7c3e2f1
上一修订: f938bb597dcc
创建时间: 2026-04-24 18:45:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Alembic 使用的修订标识。
revision: str = "a4d9b7c3e2f1"
down_revision: Union[str, Sequence[str], None] = "f938bb597dcc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """升级 schema。"""
    op.add_column("users", sa.Column("username", sa.String(length=64), nullable=True))
    op.add_column(
        "users",
        sa.Column("display_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "is_test_user",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.execute(
        """
        UPDATE users
        SET username = 'user-' || id,
            display_name = 'User ' || id
        WHERE username IS NULL
        """
    )

    op.alter_column("users", "username", nullable=False)
    op.alter_column("users", "display_name", nullable=False)
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_column("users", "email")
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)

    op.execute(
        """
        INSERT INTO users (username, display_name, is_test_user)
        VALUES
          ('demo', 'Demo User', false),
          ('sandbox', 'Sandbox User', false),
          ('test', 'Pytest User', true)
        ON CONFLICT (username) DO NOTHING
        """
    )

    for table_name in (
        "resumes",
        "job_postings",
        "match_results",
        "generated_artifacts",
        "application_records",
    ):
        op.add_column(table_name, sa.Column("user_id", sa.Integer(), nullable=True))
        op.execute(
            sa.text(
                f"""
                UPDATE {table_name}
                SET user_id = (SELECT id FROM users WHERE username = 'demo')
                WHERE user_id IS NULL
                """
            )
        )
        op.alter_column(table_name, "user_id", nullable=False)
        op.create_foreign_key(
            f"fk_{table_name}_user_id_users",
            table_name,
            "users",
            ["user_id"],
            ["id"],
        )
        op.create_index(op.f(f"ix_{table_name}_user_id"), table_name, ["user_id"])


def downgrade() -> None:
    """降级 schema。"""
    for table_name in (
        "application_records",
        "generated_artifacts",
        "match_results",
        "job_postings",
        "resumes",
    ):
        op.drop_index(op.f(f"ix_{table_name}_user_id"), table_name=table_name)
        op.drop_constraint(f"fk_{table_name}_user_id_users", table_name, type_="foreignkey")
        op.drop_column(table_name, "user_id")

    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.add_column("users", sa.Column("email", sa.String(length=255), nullable=True))
    op.execute(
        """
        UPDATE users
        SET email = username || '@legacy.local'
        WHERE email IS NULL
        """
    )
    op.alter_column("users", "email", nullable=False)
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.drop_column("users", "updated_at")
    op.drop_column("users", "created_at")
    op.drop_column("users", "is_test_user")
    op.drop_column("users", "display_name")
    op.drop_column("users", "username")
