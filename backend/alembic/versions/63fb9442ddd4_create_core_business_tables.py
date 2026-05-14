"""创建核心业务表

修订 ID: 63fb9442ddd4
上一修订: 768a3418a62d
创建时间: 2026-04-22 11:32:54.752511

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# Alembic 使用的修订标识。
revision: str = '63fb9442ddd4'
down_revision: Union[str, Sequence[str], None] = '768a3418a62d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """升级 schema。"""
    # ### Alembic 自动生成的命令，请按需调整。 ###
    op.create_table('job_postings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('company_name', sa.String(length=255), nullable=False),
    sa.Column('job_title', sa.String(length=255), nullable=False),
    sa.Column('city', sa.String(length=100), nullable=True),
    sa.Column('source_url', sa.String(length=1024), nullable=True),
    sa.Column('jd_text', sa.Text(), nullable=False),
    sa.Column('parsed_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('status', sa.String(length=50), server_default='active', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('resumes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('source_file_url', sa.String(length=1024), nullable=True),
    sa.Column('source_type', sa.String(length=50), server_default='upload', nullable=False),
    sa.Column('raw_text', sa.Text(), nullable=False),
    sa.Column('parsed_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('parse_status', sa.String(length=50), server_default='pending', nullable=False),
    sa.Column('content_hash', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_resumes_content_hash'), 'resumes', ['content_hash'], unique=False)
    op.create_table('application_records',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('resume_id', sa.Integer(), nullable=False),
    sa.Column('job_posting_id', sa.Integer(), nullable=False),
    sa.Column('current_stage', sa.String(length=50), server_default='saved', nullable=False),
    sa.Column('apply_channel', sa.String(length=100), nullable=True),
    sa.Column('applied_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('next_action', sa.String(length=255), nullable=True),
    sa.Column('next_action_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['job_posting_id'], ['job_postings.id'], ),
    sa.ForeignKeyConstraint(['resume_id'], ['resumes.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_application_records_job_posting_id'), 'application_records', ['job_posting_id'], unique=False)
    op.create_index(op.f('ix_application_records_resume_id'), 'application_records', ['resume_id'], unique=False)
    op.create_table('match_results',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('resume_id', sa.Integer(), nullable=False),
    sa.Column('job_posting_id', sa.Integer(), nullable=False),
    sa.Column('overall_score', sa.Float(), nullable=False),
    sa.Column('strengths', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('weaknesses', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('missing_keywords', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('suggestions', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['job_posting_id'], ['job_postings.id'], ),
    sa.ForeignKeyConstraint(['resume_id'], ['resumes.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_match_results_job_posting_id'), 'match_results', ['job_posting_id'], unique=False)
    op.create_index(op.f('ix_match_results_resume_id'), 'match_results', ['resume_id'], unique=False)
    # ### Alembic 命令结束。 ###


def downgrade() -> None:
    """降级 schema。"""
    # ### Alembic 自动生成的命令，请按需调整。 ###
    op.drop_index(op.f('ix_match_results_resume_id'), table_name='match_results')
    op.drop_index(op.f('ix_match_results_job_posting_id'), table_name='match_results')
    op.drop_table('match_results')
    op.drop_index(op.f('ix_application_records_resume_id'), table_name='application_records')
    op.drop_index(op.f('ix_application_records_job_posting_id'), table_name='application_records')
    op.drop_table('application_records')
    op.drop_index(op.f('ix_resumes_content_hash'), table_name='resumes')
    op.drop_table('resumes')
    op.drop_table('job_postings')
    # ### Alembic 命令结束。 ###
