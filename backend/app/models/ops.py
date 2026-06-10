# 作用：定义运营报表快照表，保存 OpsAgent 生成的经营分析结果。
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.types import GUID


class OpsReport(Base):
    """运营报表快照表。"""

    __tablename__ = "ops_reports"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    report_type: Mapped[str] = mapped_column(String(32), default="snapshot")
    order_count: Mapped[int] = mapped_column(default=0)
    revenue_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"))
    after_sales_open_count: Mapped[int] = mapped_column(default=0)
    pending_approval_count: Mapped[int] = mapped_column(default=0)
    review_count: Mapped[int] = mapped_column(default=0)
    average_rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    negative_review_count: Mapped[int] = mapped_column(default=0)
    suggestions: Mapped[list[str] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
