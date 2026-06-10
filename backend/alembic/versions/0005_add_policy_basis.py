"""add after_sales_tickets.policy_basis column

Revision ID: 0005_add_policy_basis
Revises: 0004_add_user_role
Create Date: 2026-05-31
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_add_policy_basis"
down_revision: str | None = "0004_add_user_role"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("after_sales_tickets", sa.Column("policy_basis", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("after_sales_tickets", "policy_basis")
