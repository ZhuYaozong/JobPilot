"""扩展工具调用日志以支持 MCP 来源

修订 ID: d4a7c9e2b610
上一修订: c7e2a1f34b89
创建时间: 2026-07-23 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d4a7c9e2b610"
down_revision: Union[str, Sequence[str], None] = "c7e2a1f34b89"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """允许 MCP 入站调用在没有 AgentRun 时独立留审计记录。"""
    op.alter_column("tool_call_logs", "agent_run_id", nullable=True)
    op.add_column(
        "tool_call_logs",
        sa.Column(
            "source",
            sa.String(length=20),
            nullable=False,
            server_default="assistant",
        ),
    )
    op.add_column(
        "tool_call_logs",
        sa.Column("client_id", sa.String(length=255), nullable=True),
    )
    op.create_index(
        op.f("ix_tool_call_logs_source"),
        "tool_call_logs",
        ["source"],
        unique=False,
    )


def downgrade() -> None:
    """回滚前先删除无法关联 AgentRun 的 MCP 审计记录。"""
    op.execute("DELETE FROM tool_call_logs WHERE agent_run_id IS NULL")
    op.drop_index(op.f("ix_tool_call_logs_source"), table_name="tool_call_logs")
    op.drop_column("tool_call_logs", "client_id")
    op.drop_column("tool_call_logs", "source")
    op.alter_column("tool_call_logs", "agent_run_id", nullable=False)
