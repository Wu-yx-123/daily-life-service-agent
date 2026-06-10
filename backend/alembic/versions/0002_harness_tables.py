# 作用：创建 Harness 工程化表，包括审批、风控、工具调用和回滚日志。
"""harness tables

Revision ID: 0002_harness
Revises: 0001_core_booking
Create Date: 2026-05-30
"""

from alembic import op
import sqlalchemy as sa

from app.core.types import GUID

revision = "0002_harness"
down_revision = "0001_core_booking"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "approval_requests",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("trace_id", sa.String(128), nullable=False),
        sa.Column("session_id", sa.String(128), nullable=True),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("approval_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("risk_level", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("order_id", GUID(), nullable=True),
        sa.Column("reviewer_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_approval_requests_trace_id", "approval_requests", ["trace_id"])
    op.create_table(
        "risk_records",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("trace_id", sa.String(128), nullable=False),
        sa.Column("session_id", sa.String(128), nullable=True),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("risk_level", sa.String(32), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=True),
        sa.Column("action", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_risk_records_trace_id", "risk_records", ["trace_id"])
    op.create_table(
        "tool_call_logs",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("trace_id", sa.String(128), nullable=False),
        sa.Column("session_id", sa.String(128), nullable=True),
        sa.Column("agent_name", sa.String(128), nullable=False),
        sa.Column("tool_name", sa.String(128), nullable=False),
        sa.Column("tool_args", sa.JSON(), nullable=True),
        sa.Column("tool_result", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="success"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_tool_call_logs_trace_id", "tool_call_logs", ["trace_id"])
    op.create_table(
        "rollback_logs",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("trace_id", sa.String(128), nullable=True),
        sa.Column("rollback_type", sa.String(64), nullable=False),
        sa.Column("target_ref", sa.String(128), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="success"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_rollback_logs_trace_id", "rollback_logs", ["trace_id"])


def downgrade():
    op.drop_index("ix_rollback_logs_trace_id", table_name="rollback_logs")
    op.drop_table("rollback_logs")
    op.drop_index("ix_tool_call_logs_trace_id", table_name="tool_call_logs")
    op.drop_table("tool_call_logs")
    op.drop_index("ix_risk_records_trace_id", table_name="risk_records")
    op.drop_table("risk_records")
    op.drop_index("ix_approval_requests_trace_id", table_name="approval_requests")
    op.drop_table("approval_requests")
