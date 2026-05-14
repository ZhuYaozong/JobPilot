"""创建 users 表

修订 ID: 768a3418a62d
上一修订:
创建时间: 2026-04-21 22:55:42.212597

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Alembic 使用的修订标识。
revision: str = '768a3418a62d'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """升级 schema。"""
    # ### Alembic 自动生成的命令，请按需调整。 ###
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    # ### Alembic 命令结束。 ###


def downgrade() -> None:
    """降级 schema。"""
    # ### Alembic 自动生成的命令，请按需调整。 ###
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    # ### Alembic 命令结束。 ###
