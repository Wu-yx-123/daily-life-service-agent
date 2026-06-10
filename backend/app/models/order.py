# 作用：定义订单 ORM 模型，保存用户确认后的正式预约订单。
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.types import GUID


class Order(Base):
    """订单表：确认预约后由 OrderService 写入。"""

    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"))
    store_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("stores.id"))
    service_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("services.id"))
    technician_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("technicians.id"))
    room_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("rooms.id"))
    appointment_start: Mapped[datetime] = mapped_column(DateTime)
    appointment_end: Mapped[datetime] = mapped_column(DateTime)
    original_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    final_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(32), default="agent")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
