"""add user_preferences

Revision ID: 0008_add_user_preferences
Revises: 0007_add_resume_state
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.types import GUID

revision: str = "0008_add_user_preferences"
down_revision: str | None = "0007_add_resume_state"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # user_preferences 保存结构化长期记忆；每条记录代表一个用户偏好事实。
    op.create_table(
        "user_preferences",
        # 使用项目统一 GUID 类型，兼容当前 PostgreSQL UUID 建模。
        sa.Column("id", GUID(), nullable=False),
        sa.Column("user_id", GUID(), nullable=False),
        # preference_type/value 组合表达“某类偏好等于某值”。
        sa.Column("preference_type", sa.String(64), nullable=False),
        sa.Column("preference_value", sa.String(128), nullable=False),
        # confidence + seen_count 用于区分弱记忆和强偏好。
        sa.Column("confidence", sa.Numeric(3, 2), nullable=False),
        sa.Column("seen_count", sa.Integer(), nullable=False),
        # source/evidence 保证记忆来源可解释、可审计。
        sa.Column("source", sa.String(64), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "preference_type", "preference_value", name="uq_user_preference_value"),
    )
    # 召回长期记忆时主要按 user_id + preference_type 查询。
    op.create_index("ix_user_preferences_user_type", "user_preferences", ["user_id", "preference_type"])


def downgrade() -> None:
    # 回滚时先删索引再删表，保持与 upgrade 创建顺序相反。
    op.drop_index("ix_user_preferences_user_type", table_name="user_preferences")
    op.drop_table("user_preferences")
