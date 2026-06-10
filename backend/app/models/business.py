# 作用：定义 Phase 1 业务基础 ORM 模型，包括用户、门店、服务、技师、房间和排班。
import uuid
from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Numeric, String, Text, Time, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.types import GUID


class User(Base):
    """用户表：Phase 1 只保存预约所需的基础用户信息。"""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    username: Mapped[str | None] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(256))
    phone: Mapped[str | None] = mapped_column(String(32), unique=True)
    nickname: Mapped[str | None] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(32), default="customer")  # customer | merchant
    member_level: Mapped[str | None] = mapped_column(String(32))
    default_location: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class Store(Base):
    """门店表：包含营业时间，供排班校验使用。"""

    __tablename__ = "stores"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    latitude: Mapped[float | None]
    longitude: Mapped[float | None]
    opening_time: Mapped[time] = mapped_column(Time, nullable=False)
    closing_time: Mapped[time] = mapped_column(Time, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    services: Mapped[list["Service"]] = relationship(back_populates="store")
    technicians: Mapped[list["Technician"]] = relationship(back_populates="store")
    rooms: Mapped[list["Room"]] = relationship(back_populates="store")


class Service(Base):
    """服务项目表：用于 MatchAgent 匹配服务和 PriceAgent 计算价格。"""

    __tablename__ = "services"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("stores.id"))
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str | None] = mapped_column(String(64))
    duration_minutes: Mapped[int]
    base_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    description: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    store: Mapped[Store] = relationship(back_populates="services")


class Technician(Base):
    """技师表：技能标签和评分会参与候选方案排序。"""

    __tablename__ = "technicians"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("stores.id"))
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    skill_tags: Mapped[list[str] | None] = mapped_column(JSON)
    rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    store: Mapped[Store] = relationship(back_populates="technicians")


class Room(Base):
    """房间表：ScheduleAgent 会为可用预约分配一个空闲房间。"""

    __tablename__ = "rooms"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    store_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("stores.id"))
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    room_type: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="active")

    store: Mapped[Store] = relationship(back_populates="rooms")


class TechnicianSchedule(Base):
    """技师排班表：用于判断技师在目标时间段是否上班。"""

    __tablename__ = "technician_schedules"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    technician_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("technicians.id"))
    store_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("stores.id"))
    work_date: Mapped[date] = mapped_column(Date)
    start_time: Mapped[datetime] = mapped_column(DateTime)
    end_time: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(32), default="available")


class Coupon(Base):
    """优惠券表：Phase 1 先建模，复杂优惠规则留到后续阶段。"""

    __tablename__ = "coupons"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"))
    title: Mapped[str | None] = mapped_column(String(128))
    discount_type: Mapped[str | None] = mapped_column(String(32))
    discount_value: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    min_order_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    valid_from: Mapped[datetime | None] = mapped_column(DateTime)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(32), default="unused")


class Review(Base):
    """评价表：Phase 1 先建模，后续可用于推荐排序和运营分析。"""

    __tablename__ = "reviews"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    order_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("orders.id"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"))
    rating: Mapped[int]
    content: Mapped[str | None] = mapped_column(Text)
    sentiment: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class KnowledgeDocument(Base):
    """知识库文档表：保存门店规则、售后政策和服务说明。"""

    __tablename__ = "knowledge_documents"

    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
