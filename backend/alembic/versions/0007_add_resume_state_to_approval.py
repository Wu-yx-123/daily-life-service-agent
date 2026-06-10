"""add resume_state, resume_step to approval_requests

Revision ID: 0007_add_resume_state
Revises: 0006_enhance_tool_call_logs
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_add_resume_state"
down_revision: str | None = "0006_enhance_tool_call_logs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("approval_requests", sa.Column("resume_state", sa.JSON(), nullable=True))
    op.add_column("approval_requests", sa.Column("resume_step", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("approval_requests", "resume_step")
    op.drop_column("approval_requests", "resume_state")
