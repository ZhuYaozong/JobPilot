"""创建工作流层表

修订 ID: 5d21bc9bb45b
上一修订: 63fb9442ddd4
创建时间: 2026-04-22 15:41:23.515244

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Alembic 使用的修订标识。
revision: str = '5d21bc9bb45b'
down_revision: Union[str, Sequence[str], None] = '63fb9442ddd4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """升级 schema。"""
    # ### Alembic 自动生成的命令，请按需调整。 ###
    op.create_table('resume_versions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('resume_id', sa.Integer(), nullable=False),
    sa.Column('job_posting_id', sa.Integer(), nullable=True),
    sa.Column('version_no', sa.Integer(), nullable=False),
    sa.Column('version_label', sa.String(length=255), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('content_format', sa.String(length=50), server_default='markdown', nullable=False),
    sa.Column('source_type', sa.String(length=50), server_default='manual', nullable=False),
    sa.Column('change_summary', sa.Text(), nullable=True),
    sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['job_posting_id'], ['job_postings.id'], ),
    sa.ForeignKeyConstraint(['resume_id'], ['resumes.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_resume_versions_job_posting_id'), 'resume_versions', ['job_posting_id'], unique=False)
    op.create_index(op.f('ix_resume_versions_resume_id'), 'resume_versions', ['resume_id'], unique=False)
    op.create_table('application_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('application_record_id', sa.Integer(), nullable=False),
    sa.Column('event_type', sa.String(length=50), nullable=False),
    sa.Column('from_stage', sa.String(length=50), nullable=True),
    sa.Column('to_stage', sa.String(length=50), nullable=True),
    sa.Column('event_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('operator_type', sa.String(length=50), server_default='user', nullable=False),
    sa.Column('payload_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['application_record_id'], ['application_records.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_application_events_application_record_id'), 'application_events', ['application_record_id'], unique=False)
    # ### Alembic 命令结束。 ###


def downgrade() -> None:
    """降级 schema。"""
    # ### Alembic 自动生成的命令，请按需调整。 ###
    op.drop_index(op.f('ix_application_events_application_record_id'), table_name='application_events')
    op.drop_table('application_events')
    op.drop_index(op.f('ix_resume_versions_resume_id'), table_name='resume_versions')
    op.drop_index(op.f('ix_resume_versions_job_posting_id'), table_name='resume_versions')
    op.drop_table('resume_versions')
    # ### Alembic 命令结束。 ###
