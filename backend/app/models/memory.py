# 作用：定义用户长期记忆模型，保存可解释、可追溯的结构化偏好。
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.types import GUID


class UserPreference(Base):
    """用户长期偏好表。

    每条记录是一类稳定偏好，例如服务类型、力度、预算、常用时段或技师偏好。
    confidence 和 seen_count 用来避免把单次表达过早固化成强记忆。
    """

    __tablename__ = "user_preferences"
    __table_args__ = (
        # 同一个用户的同一类偏好值只保留一条记录，重复出现时提升 seen_count/confidence。
        UniqueConstraint("user_id", "preference_type", "preference_value", name="uq_user_preference_value"),
    )

    # 偏好自身的主键，便于后续做删除、审计或用户隐私导出。
    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    # 归属用户；长期记忆必须始终绑定用户，不能跨用户共享。
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    # 偏好类型，例如 service_type / strength / budget_max / technician_name / time_window。
    preference_type: Mapped[str] = mapped_column(String(64), nullable=False)
    # 偏好值统一存成字符串，方便不同偏好类型共用同一张表。
    preference_value: Mapped[str] = mapped_column(String(128), nullable=False)
    # 置信度越高，越适合在下一轮预约里作为默认偏好召回。
    confidence: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=Decimal("0.55"), nullable=False)
    # 出现次数用于区分“偶然表达”和“稳定偏好”。
    seen_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # 来源记录这条记忆来自预约确认、评价、售后还是其他链路。
    source: Mapped[str] = mapped_column(String(64), default="booking", nullable=False)
    # 证据链保存 trace_id/order_id/message 摘要，保证记忆可追溯。
    evidence: Mapped[dict | None] = mapped_column(JSON)
    # last_seen_at 用来判断偏好新鲜度，后续可做衰减或过期。
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
