# 作用：商家管理后台 API，覆盖门店、服务、技师、房间、排班、订单、评价的 CRUD 和运营面板。
from datetime import date, datetime, time
from decimal import Decimal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.business import (
    Coupon,
    Review,
    Room,
    Service,
    Store,
    Technician,
    TechnicianSchedule,
    User,
)
from app.models.order import Order

router = APIRouter(prefix="/admin", tags=["admin"])

# ═══════════════════════════════════════════════════════════════════
# Schemas
# ═══════════════════════════════════════════════════════════════════


class DashboardMetrics(BaseModel):
    total_orders: int
    total_revenue: float
    orders_today: int
    revenue_today: float
    active_services: int
    active_technicians: int
    open_after_sales: int
    pending_approvals: int
    average_rating: float | None
    recent_orders: list[dict]


class ServiceIn(BaseModel):
    name: str
    category: str | None = None
    duration_minutes: int
    base_price: float
    description: str | None = None
    tags: list[str] | None = None


class TechnicianIn(BaseModel):
    name: str
    skill_tags: list[str] | None = None
    rating: float | None = None


class RoomIn(BaseModel):
    name: str
    room_type: str | None = None


class ScheduleIn(BaseModel):
    technician_id: str
    work_date: str  # YYYY-MM-DD
    start_time: str  # ISO datetime
    end_time: str


class OrderStatusUpdate(BaseModel):
    status: str  # confirmed | cancelled | completed | refunded


# ═══════════════════════════════════════════════════════════════════
# Dashboard
# ═══════════════════════════════════════════════════════════════════


@router.get("/dashboard", response_model=DashboardMetrics)
async def dashboard(db: AsyncSession = Depends(get_db)):
    now = datetime.now()
    today_start = datetime.combine(now.date(), time.min)
    store = (await db.scalars(select(Store).where(Store.status == "active").limit(1))).first()
    store_id = store.id if store else None

    total_orders = await db.scalar(select(func.count()).select_from(Order).where(Order.status == "confirmed")) or 0
    total_revenue = await db.scalar(select(func.coalesce(func.sum(Order.final_price), 0)).where(Order.status == "confirmed")) or 0
    orders_today = await db.scalar(select(func.count()).select_from(Order).where(Order.status == "confirmed", Order.created_at >= today_start)) or 0
    revenue_today = await db.scalar(select(func.coalesce(func.sum(Order.final_price), 0)).where(Order.status == "confirmed", Order.created_at >= today_start)) or 0
    active_services = await db.scalar(select(func.count()).select_from(Service).where(Service.status == "active")) or 0
    active_technicians = await db.scalar(select(func.count()).select_from(Technician).where(Technician.status == "active")) or 0

    from app.models.after_sales import AfterSalesTicket
    from app.models.approval import ApprovalRequest
    open_as = await db.scalar(select(func.count()).select_from(AfterSalesTicket).where(AfterSalesTicket.status == "open")) or 0
    pending_ap = await db.scalar(select(func.count()).select_from(ApprovalRequest).where(ApprovalRequest.status == "pending")) or 0
    avg_rating = await db.scalar(select(func.avg(Review.rating))) or 0
    avg_rating_f = float(avg_rating) if avg_rating else None

    recent = (await db.scalars(select(Order).order_by(Order.created_at.desc()).limit(5))).all()
    recent_orders = [
        {
            "id": str(o.id), "status": o.status,
            "final_price": float(o.final_price),
            "appointment_start": o.appointment_start.isoformat() if o.appointment_start else None,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        }
        for o in recent
    ]

    return DashboardMetrics(
        total_orders=total_orders, total_revenue=float(total_revenue),
        orders_today=orders_today, revenue_today=float(revenue_today),
        active_services=active_services, active_technicians=active_technicians,
        open_after_sales=open_as, pending_approvals=pending_ap,
        average_rating=avg_rating_f, recent_orders=recent_orders,
    )


# ═══════════════════════════════════════════════════════════════════
# Services CRUD
# ═══════════════════════════════════════════════════════════════════


@router.get("/services")
async def list_services(db: AsyncSession = Depends(get_db)):
    svcs = (await db.scalars(select(Service).where(Service.status != "inactive").order_by(Service.category, Service.name))).all()
    return [{"id": str(s.id), "store_id": str(s.store_id), "name": s.name, "category": s.category,
             "duration_minutes": s.duration_minutes, "base_price": float(s.base_price),
             "description": s.description, "tags": s.tags, "status": s.status} for s in svcs]


@router.post("/services")
async def create_service(payload: ServiceIn, db: AsyncSession = Depends(get_db)):
    store = (await db.scalars(select(Store).where(Store.status == "active").limit(1))).first()
    if not store:
        raise HTTPException(400, "无活跃门店，请先创建门店")
    svc = Service(store_id=store.id, name=payload.name, category=payload.category,
                  duration_minutes=payload.duration_minutes, base_price=Decimal(str(payload.base_price)),
                  description=payload.description, tags=payload.tags or [], status="active")
    db.add(svc)
    await db.flush()
    await db.commit()
    return {"id": str(svc.id), "name": svc.name}


@router.put("/services/{service_id}")
async def update_service(service_id: str, payload: ServiceIn, db: AsyncSession = Depends(get_db)):
    svc = await db.get(Service, service_id)
    if not svc:
        raise HTTPException(404, "服务不存在")
    svc.name = payload.name
    svc.category = payload.category
    svc.duration_minutes = payload.duration_minutes
    svc.base_price = Decimal(str(payload.base_price))
    svc.description = payload.description
    svc.tags = payload.tags or []
    await db.commit()
    return {"id": str(svc.id), "name": svc.name}


@router.delete("/services/{service_id}")
async def delete_service(service_id: str, db: AsyncSession = Depends(get_db)):
    svc = await db.get(Service, service_id)
    if not svc:
        raise HTTPException(404, "服务不存在")
    svc.status = "inactive"
    await db.commit()
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════
# Technicians CRUD
# ═══════════════════════════════════════════════════════════════════


@router.get("/technicians")
async def list_technicians(db: AsyncSession = Depends(get_db)):
    techs = (await db.scalars(select(Technician).where(Technician.status != "inactive").order_by(Technician.name))).all()
    return [{"id": str(t.id), "store_id": str(t.store_id), "name": t.name,
             "skill_tags": t.skill_tags, "rating": float(t.rating) if t.rating else None,
             "status": t.status} for t in techs]


@router.post("/technicians")
async def create_technician(payload: TechnicianIn, db: AsyncSession = Depends(get_db)):
    store = (await db.scalars(select(Store).where(Store.status == "active").limit(1))).first()
    if not store:
        raise HTTPException(400, "无活跃门店")
    tech = Technician(store_id=store.id, name=payload.name,
                      skill_tags=payload.skill_tags or [], rating=Decimal(str(payload.rating or 0)), status="active")
    db.add(tech)
    await db.flush()
    await db.commit()
    return {"id": str(tech.id), "name": tech.name}


@router.put("/technicians/{tech_id}")
async def update_technician(tech_id: str, payload: TechnicianIn, db: AsyncSession = Depends(get_db)):
    tech = await db.get(Technician, tech_id)
    if not tech:
        raise HTTPException(404, "技师不存在")
    tech.name = payload.name
    tech.skill_tags = payload.skill_tags or []
    if payload.rating is not None:
        tech.rating = Decimal(str(payload.rating))
    await db.commit()
    return {"id": str(tech.id), "name": tech.name}


@router.delete("/technicians/{tech_id}")
async def delete_technician(tech_id: str, db: AsyncSession = Depends(get_db)):
    tech = await db.get(Technician, tech_id)
    if not tech:
        raise HTTPException(404, "技师不存在")
    tech.status = "inactive"
    await db.commit()
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════
# Rooms CRUD
# ═══════════════════════════════════════════════════════════════════


@router.get("/rooms")
async def list_rooms(db: AsyncSession = Depends(get_db)):
    rooms = (await db.scalars(select(Room).order_by(Room.name))).all()
    return [{"id": str(r.id), "store_id": str(r.store_id), "name": r.name,
             "room_type": r.room_type, "status": r.status} for r in rooms]


@router.post("/rooms")
async def create_room(payload: RoomIn, db: AsyncSession = Depends(get_db)):
    store = (await db.scalars(select(Store).where(Store.status == "active").limit(1))).first()
    if not store:
        raise HTTPException(400, "无活跃门店")
    room = Room(store_id=store.id, name=payload.name, room_type=payload.room_type, status="active")
    db.add(room)
    await db.flush()
    await db.commit()
    return {"id": str(room.id), "name": room.name}


@router.put("/rooms/{room_id}")
async def update_room(room_id: str, payload: RoomIn, db: AsyncSession = Depends(get_db)):
    room = await db.get(Room, room_id)
    if not room:
        raise HTTPException(404, "房间不存在")
    room.name = payload.name
    room.room_type = payload.room_type
    await db.commit()
    return {"id": str(room.id), "name": room.name}


@router.delete("/rooms/{room_id}")
async def delete_room(room_id: str, db: AsyncSession = Depends(get_db)):
    room = await db.get(Room, room_id)
    if not room:
        raise HTTPException(404, "房间不存在")
    room.status = "inactive"
    await db.commit()
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════
# Schedules
# ═══════════════════════════════════════════════════════════════════


@router.get("/schedules")
async def list_schedules(db: AsyncSession = Depends(get_db)):
    stmt = select(TechnicianSchedule).order_by(TechnicianSchedule.work_date, TechnicianSchedule.start_time)
    items = (await db.scalars(stmt)).all()
    return [{"id": str(s.id), "technician_id": str(s.technician_id), "store_id": str(s.store_id),
             "work_date": s.work_date.isoformat() if s.work_date else None,
             "start_time": s.start_time.isoformat() if s.start_time else None,
             "end_time": s.end_time.isoformat() if s.end_time else None, "status": s.status} for s in items]


@router.post("/schedules")
async def create_schedule(payload: ScheduleIn, db: AsyncSession = Depends(get_db)):
    store = (await db.scalars(select(Store).where(Store.status == "active").limit(1))).first()
    if not store:
        raise HTTPException(400, "无活跃门店")
    tech = await db.get(Technician, payload.technician_id)
    if not tech:
        raise HTTPException(404, "技师不存在")
    sched = TechnicianSchedule(
        technician_id=payload.technician_id, store_id=store.id,
        work_date=date.fromisoformat(payload.work_date),
        start_time=datetime.fromisoformat(payload.start_time),
        end_time=datetime.fromisoformat(payload.end_time), status="available",
    )
    db.add(sched)
    await db.flush()
    await db.commit()
    return {"id": str(sched.id), "work_date": sched.work_date.isoformat()}


@router.delete("/schedules/{sched_id}")
async def delete_schedule(sched_id: str, db: AsyncSession = Depends(get_db)):
    sched = await db.get(TechnicianSchedule, sched_id)
    if not sched:
        raise HTTPException(404, "排班不存在")
    await db.delete(sched)
    await db.commit()
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════
# Store
# ═══════════════════════════════════════════════════════════════════


@router.get("/store")
async def get_store(db: AsyncSession = Depends(get_db)):
    store = (await db.scalars(select(Store).where(Store.status == "active").limit(1))).first()
    if not store:
        return {"id": None, "name": "未配置"}
    return {"id": str(store.id), "name": store.name, "address": store.address,
            "opening_time": store.opening_time.isoformat(), "closing_time": store.closing_time.isoformat(),
            "latitude": store.latitude, "longitude": store.longitude}


class StoreUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    opening_time: str | None = None  # HH:MM
    closing_time: str | None = None


@router.put("/store")
async def update_store(payload: StoreUpdate, db: AsyncSession = Depends(get_db)):
    store = (await db.scalars(select(Store).where(Store.status == "active").limit(1))).first()
    if not store:
        raise HTTPException(404, "门店不存在")
    if payload.name is not None:
        store.name = payload.name
    if payload.address is not None:
        store.address = payload.address
    if payload.latitude is not None:
        store.latitude = payload.latitude
    if payload.longitude is not None:
        store.longitude = payload.longitude
    if payload.opening_time is not None:
        store.opening_time = time.fromisoformat(payload.opening_time)
    if payload.closing_time is not None:
        store.closing_time = time.fromisoformat(payload.closing_time)
    await db.commit()
    return {"id": str(store.id), "name": store.name}


# ═══════════════════════════════════════════════════════════════════
# Orders
# ═══════════════════════════════════════════════════════════════════


@router.get("/orders")
async def list_orders(status: str | None = None, limit: int = 50, db: AsyncSession = Depends(get_db)):
    stmt = select(Order).order_by(Order.created_at.desc())
    if status:
        stmt = stmt.where(Order.status == status)
    orders = (await db.scalars(stmt.limit(limit))).all()
    return [{"id": str(o.id), "user_id": str(o.user_id) if o.user_id else None,
             "store_id": str(o.store_id) if o.store_id else None,
             "service_id": str(o.service_id) if o.service_id else None,
             "technician_id": str(o.technician_id) if o.technician_id else None,
             "room_id": str(o.room_id) if o.room_id else None,
             "appointment_start": o.appointment_start.isoformat() if o.appointment_start else None,
             "appointment_end": o.appointment_end.isoformat() if o.appointment_end else None,
             "original_price": float(o.original_price), "final_price": float(o.final_price),
             "status": o.status, "created_at": o.created_at.isoformat() if o.created_at else None}
            for o in orders]


@router.get("/orders/{order_id}")
async def get_order(order_id: str, db: AsyncSession = Depends(get_db)):
    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(404, "订单不存在")
    return {"id": str(order.id), "user_id": str(order.user_id) if order.user_id else None,
            "service_id": str(order.service_id) if order.service_id else None,
            "technician_id": str(order.technician_id) if order.technician_id else None,
            "room_id": str(order.room_id) if order.room_id else None,
            "appointment_start": order.appointment_start.isoformat() if order.appointment_start else None,
            "appointment_end": order.appointment_end.isoformat() if order.appointment_end else None,
            "original_price": float(order.original_price), "final_price": float(order.final_price),
            "status": order.status}


@router.put("/orders/{order_id}")
async def update_order_status(order_id: str, payload: OrderStatusUpdate, db: AsyncSession = Depends(get_db)):
    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(404, "订单不存在")
    order.status = payload.status
    await db.commit()
    return {"id": str(order.id), "status": order.status}


# ═══════════════════════════════════════════════════════════════════
# Reviews
# ═══════════════════════════════════════════════════════════════════


@router.get("/reviews")
async def list_reviews(limit: int = 50, db: AsyncSession = Depends(get_db)):
    reviews = (await db.scalars(select(Review).order_by(Review.created_at.desc()).limit(limit))).all()
    return [{"id": str(r.id), "order_id": str(r.order_id) if r.order_id else None,
             "user_id": str(r.user_id) if r.user_id else None, "rating": r.rating,
             "content": r.content, "sentiment": r.sentiment,
             "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in reviews]
