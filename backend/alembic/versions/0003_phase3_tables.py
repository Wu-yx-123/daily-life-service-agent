# 作用：创建 Phase 3 业务扩展表，包括售后、评价、知识库和运营报表。
"""phase3 tables

Revision ID: 0003_phase3
Revises: 0002_harness
Create Date: 2026-05-30
"""

from alembic import op
import sqlalchemy as sa

from app.core.types import GUID

revision = "0003_phase3"
down_revision = "0002_harness"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "after_sales_tickets",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("trace_id", sa.String(128), nullable=False),
        sa.Column("session_id", sa.String(128), nullable=True),
        sa.Column("user_id", sa.String(128), nullable=False),
        sa.Column("ticket_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="open"),
        sa.Column("priority", sa.String(32), nullable=False, server_default="normal"),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("suggested_action", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_after_sales_tickets_trace_id", "after_sales_tickets", ["trace_id"])
    op.create_table(
        "reviews",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("order_id", GUID(), sa.ForeignKey("orders.id"), nullable=True),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("sentiment", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "knowledge_documents",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_table(
        "ops_reports",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("report_type", sa.String(32), nullable=False, server_default="snapshot"),
        sa.Column("order_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("revenue_total", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("after_sales_open_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pending_approval_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("review_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("average_rating", sa.Numeric(3, 2), nullable=True),
        sa.Column("negative_review_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("suggestions", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("ops_reports")
    op.drop_table("knowledge_documents")
    op.drop_table("reviews")
    op.drop_index("ix_after_sales_tickets_trace_id", table_name="after_sales_tickets")
    op.drop_table("after_sales_tickets")
