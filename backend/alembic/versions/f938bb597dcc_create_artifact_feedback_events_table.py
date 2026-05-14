"""创建 artifact_feedback_events 表

修订 ID: f938bb597dcc
上一修订: 481b01b23f23
创建时间: 2026-04-23 20:17:01.259591

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# Alembic 使用的修订标识。
revision: str = 'f938bb597dcc'
down_revision: Union[str, Sequence[str], None] = '481b01b23f23'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """升级 schema。"""
    # ### Alembic 自动生成的命令，请按需调整。 ###
    op.create_table('artifact_feedback_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('generated_artifact_id', sa.Integer(), nullable=False),
    sa.Column('feedback_type', sa.String(length=50), nullable=False),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['generated_artifact_id'], ['generated_artifacts.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_artifact_feedback_events_generated_artifact_id'), 'artifact_feedback_events', ['generated_artifact_id'], unique=False)
    # ### Alembic 命令结束。 ###


def downgrade() -> None:
    """降级 schema。"""
    # ### Alembic 自动生成的命令，请按需调整。 ###
    op.drop_index(op.f('ix_artifact_feedback_events_generated_artifact_id'), table_name='artifact_feedback_events')
    op.drop_table('artifact_feedback_events')
    # ### Alembic 命令结束。 ###
