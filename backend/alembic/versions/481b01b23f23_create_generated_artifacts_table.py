"""创建 generated_artifacts 表

修订 ID: 481b01b23f23
上一修订: 5d21bc9bb45b
创建时间: 2026-04-22 20:44:34.579095

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Alembic 使用的修订标识。
revision: str = '481b01b23f23'
down_revision: Union[str, Sequence[str], None] = '5d21bc9bb45b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """升级 schema。"""
    # ### Alembic 自动生成的命令，请按需调整。 ###
    op.create_table('generated_artifacts',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('artifact_type', sa.String(length=50), nullable=False),
    sa.Column('resume_id', sa.Integer(), nullable=True),
    sa.Column('job_posting_id', sa.Integer(), nullable=True),
    sa.Column('application_record_id', sa.Integer(), nullable=True),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('content_text', sa.Text(), nullable=True),
    sa.Column('content_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('status', sa.String(length=50), server_default='draft', nullable=False),
    sa.Column('generator_type', sa.String(length=50), server_default='manual', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['application_record_id'], ['application_records.id'], ),
    sa.ForeignKeyConstraint(['job_posting_id'], ['job_postings.id'], ),
    sa.ForeignKeyConstraint(['resume_id'], ['resumes.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_generated_artifacts_application_record_id'), 'generated_artifacts', ['application_record_id'], unique=False)
    op.create_index(op.f('ix_generated_artifacts_job_posting_id'), 'generated_artifacts', ['job_posting_id'], unique=False)
    op.create_index(op.f('ix_generated_artifacts_resume_id'), 'generated_artifacts', ['resume_id'], unique=False)
    # ### Alembic 命令结束。 ###


def downgrade() -> None:
    """降级 schema。"""
    # ### Alembic 自动生成的命令，请按需调整。 ###
    op.drop_index(op.f('ix_generated_artifacts_resume_id'), table_name='generated_artifacts')
    op.drop_index(op.f('ix_generated_artifacts_job_posting_id'), table_name='generated_artifacts')
    op.drop_index(op.f('ix_generated_artifacts_application_record_id'), table_name='generated_artifacts')
    op.drop_table('generated_artifacts')
    # ### Alembic 命令结束。 ###
