# 作用：订单创建和查询工具，供 OrderAgent 和 CustomerServiceAgent 调用。
from app.repositories.order_repo import OrderRepository
from app.schemas.agent import OrderDraft


async def create_order(
    *,
    order_repo: OrderRepository,
    draft: dict,
    user_id: str,
    **kwargs,
) -> dict:
    """基于已确认的订单草稿创建正式订单。

    ⚠️ 此工具不直接写库；实际写入必须通过 OrderService.create_confirmed_order，
    该 service 会做数据库事务层的最后一次冲突复查。
    """
    from app.services.order_service import OrderService

    parsed = OrderDraft.model_validate(draft)
    service = OrderService(order_repo.db, order_repo)
    try:
        order = await service.create_confirmed_order(user_id=user_id, draft=parsed)
        return {
            "order_id": str(order.id),
            "status": order.status,
            "appointment_start": order.appointment_start.isoformat() if order.appointment_start else None,
            "appointment_end": order.appointment_end.isoformat() if order.appointment_end else None,
            "final_price": str(order.final_price),
        }
    except ValueError as exc:
        return {"error": str(exc)}


async def get_order(
    *,
    order_repo: OrderRepository,
    order_id: str,
    **kwargs,
) -> dict | None:
    """查询单个订单详情。"""
    from sqlalchemy import select
    from app.models.order import Order

    order = await order_repo.db.get(Order, order_id)
    if not order:
        return None
    return {
        "id": str(order.id),
        "user_id": str(order.user_id) if order.user_id else None,
        "store_id": str(order.store_id) if order.store_id else None,
        "service_id": str(order.service_id) if order.service_id else None,
        "technician_id": str(order.technician_id) if order.technician_id else None,
        "room_id": str(order.room_id) if order.room_id else None,
        "appointment_start": order.appointment_start.isoformat() if order.appointment_start else None,
        "appointment_end": order.appointment_end.isoformat() if order.appointment_end else None,
        "original_price": str(order.original_price),
        "final_price": str(order.final_price),
        "status": order.status,
    }


async def list_user_orders(
    *,
    order_repo: OrderRepository,
    user_id: str,
    status: str | None = None,
    **kwargs,
) -> list[dict]:
    """查询某个用户的历史订单。"""
    from sqlalchemy import select
    from app.models.order import Order

    stmt = select(Order).where(Order.user_id == user_id).order_by(Order.created_at.desc())
    if status:
        stmt = stmt.where(Order.status == status)
    orders = list((await order_repo.db.scalars(stmt)).all())
    return [
        {
            "id": str(o.id),
            "store_id": str(o.store_id) if o.store_id else None,
            "service_id": str(o.service_id) if o.service_id else None,
            "technician_id": str(o.technician_id) if o.technician_id else None,
            "appointment_start": o.appointment_start.isoformat() if o.appointment_start else None,
            "appointment_end": o.appointment_end.isoformat() if o.appointment_end else None,
            "final_price": str(o.final_price),
            "status": o.status,
        }
        for o in orders
    ]


async def check_order_conflicts(
    *,
    order_repo: OrderRepository,
    technician_id: str | None = None,
    room_id: str | None = None,
    start: str,
    end: str,
    **kwargs,
) -> list[dict]:
    """检查指定时间段内是否存在订单冲突。"""
    from datetime import datetime
    conflicts = await order_repo.list_overlapping_orders(
        technician_id=technician_id,
        room_id=room_id,
        start=datetime.fromisoformat(start),
        end=datetime.fromisoformat(end),
    )
    return [
        {
            "id": str(o.id),
            "technician_id": str(o.technician_id) if o.technician_id else None,
            "room_id": str(o.room_id) if o.room_id else None,
            "appointment_start": o.appointment_start.isoformat() if o.appointment_start else None,
            "appointment_end": o.appointment_end.isoformat() if o.appointment_end else None,
        }
        for o in conflicts
    ]
