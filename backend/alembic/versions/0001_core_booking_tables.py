# 作用：创建预约闭环核心表，包括用户、门店、服务、排班、订单和 Agent Trace。
"""core booking tables

Revision ID: 0001_core_booking
Revises:
Create Date: 2026-05-30
"""

from alembic import op
import sqlalchemy as sa

from app.core.types import GUID

revision = "0001_core_booking"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("phone", sa.String(32), nullable=True, unique=True),
        sa.Column("nickname", sa.String(64), nullable=True),
        sa.Column("member_level", sa.String(32), nullable=True),
        sa.Column("default_location", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "stores",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("opening_time", sa.Time(), nullable=False),
        sa.Column("closing_time", sa.Time(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "services",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("store_id", GUID(), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("base_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "technicians",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("store_id", GUID(), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("skill_tags", sa.JSON(), nullable=True),
        sa.Column("rating", sa.Numeric(3, 2), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "rooms",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("store_id", GUID(), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("room_type", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
    )
    op.create_table(
        "technician_schedules",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("technician_id", GUID(), sa.ForeignKey("technicians.id"), nullable=False),
        sa.Column("store_id", GUID(), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.DateTime(), nullable=False),
        sa.Column("end_time", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="available"),
    )
    op.create_table(
        "orders",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("store_id", GUID(), sa.ForeignKey("stores.id"), nullable=False),
        sa.Column("service_id", GUID(), sa.ForeignKey("services.id"), nullable=False),
        sa.Column("technician_id", GUID(), sa.ForeignKey("technicians.id"), nullable=False),
        sa.Column("room_id", GUID(), sa.ForeignKey("rooms.id"), nullable=False),
        sa.Column("appointment_start", sa.DateTime(), nullable=False),
        sa.Column("appointment_end", sa.DateTime(), nullable=False),
        sa.Column("original_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("final_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("source", sa.String(32), nullable=False, server_default="agent"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "agent_traces",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("trace_id", sa.String(128), nullable=False),
        sa.Column("session_id", sa.String(128), nullable=True),
        sa.Column("order_id", GUID(), nullable=True),
        sa.Column("agent_name", sa.String(128), nullable=True),
        sa.Column("step_name", sa.String(128), nullable=True),
        sa.Column("input", sa.JSON(), nullable=True),
        sa.Column("output", sa.JSON(), nullable=True),
        sa.Column("tool_name", sa.String(128), nullable=True),
        sa.Column("tool_args", sa.JSON(), nullable=True),
        sa.Column("tool_result", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(32), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_agent_traces_trace_id", "agent_traces", ["trace_id"])


def downgrade():
    op.drop_index("ix_agent_traces_trace_id", table_name="agent_traces")
    op.drop_table("agent_traces")
    op.drop_table("orders")
    op.drop_table("technician_schedules")
    op.drop_table("rooms")
    op.drop_table("technicians")
    op.drop_table("services")
    op.drop_table("stores")
    op.drop_table("users")
