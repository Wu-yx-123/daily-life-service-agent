"""add user.role column

Revision ID: 0004_add_user_role
Revises: 0003_phase3
Create Date: 2026-05-31
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_add_user_role"
down_revision: str | None = "0003_phase3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("role", sa.String(32), server_default="customer", nullable=False))


def downgrade() -> None:
    op.drop_column("users", "role")
