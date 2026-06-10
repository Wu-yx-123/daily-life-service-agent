"""enhance tool_call_logs with risk_level, retry_count, permission_denied

Revision ID: 0006_enhance_tool_call_logs
Revises: 0005_add_policy_basis
Create Date: 2026-06-01
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_enhance_tool_call_logs"
down_revision: str | None = "0005_add_policy_basis"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tool_call_logs", sa.Column("risk_level", sa.String(16), nullable=True))
    op.add_column("tool_call_logs", sa.Column("retry_count", sa.Integer(), nullable=True, server_default="0"))
    op.add_column("tool_call_logs", sa.Column("permission_denied", sa.Boolean(), nullable=True, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("tool_call_logs", "permission_denied")
    op.drop_column("tool_call_logs", "retry_count")
    op.drop_column("tool_call_logs", "risk_level")
