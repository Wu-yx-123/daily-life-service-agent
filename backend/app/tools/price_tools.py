# 作用：价格计算和优惠券查询工具，供 PriceAgent 调用。
from decimal import Decimal

from app.repositories.catalog_repo import CatalogRepository
from app.schemas.agent import PriceOutput


async def calculate_price(
    *,
    catalog_repo: CatalogRepository,
    service_id: str,
    user_id: str | None = None,
    **kwargs,
) -> PriceOutput:
    """计算服务价格并生成价格快照。

    Phase 2+: 叠加会员折扣、优惠券、满减后返回 final_price。
    """
    from app.services.price_service import PriceService

    service = PriceService(catalog_repo)
    return await service.calculate(service_id=service_id, user_id=user_id)


async def list_available_coupons(
    *,
    catalog_repo: CatalogRepository,
    user_id: str,
    **kwargs,
) -> list[dict]:
    """查询用户可用的优惠券列表。"""
    from sqlalchemy import select
    from datetime import UTC, datetime
    from app.models.business import Coupon

    now = datetime.now(UTC).replace(tzinfo=None)
    stmt = (
        select(Coupon)
        .where(Coupon.user_id == user_id)
        .where(Coupon.status == "unused")
        .where(Coupon.valid_from <= now)
        .where(Coupon.valid_to >= now)
    )
    coupons = list((await catalog_repo.db.scalars(stmt)).all())
    return [
        {
            "id": str(c.id),
            "title": c.title,
            "discount_type": c.discount_type,
            "discount_value": float(c.discount_value) if c.discount_value else 0,
            "min_order_amount": float(c.min_order_amount) if c.min_order_amount else 0,
            "valid_to": c.valid_to.isoformat() if c.valid_to else None,
        }
        for c in coupons
    ]


async def calculate_discounted_price(
    *,
    catalog_repo: CatalogRepository,
    service_id: str,
    user_id: str,
    coupon_id: str | None = None,
    **kwargs,
) -> PriceOutput:
    """计算叠加折扣后的最终价格。

    计算顺序：原价 → 会员折扣 → 优惠券 → 满减促销 → final_price。
    """
    from datetime import UTC, datetime
    from app.services.price_service import PriceService

    service_obj = await catalog_repo.get_service(service_id)
    if not service_obj:
        raise ValueError("service not found")
    original = Decimal(service_obj.base_price)
    member_discount = Decimal("0")
    coupon_discount = Decimal("0")
    promotion_discount = Decimal("0")

    # 会员折扣：MVP 按用户 member_level 拉取，Phase 2+ 可改成查价表。
    # 此处预留逻辑框架。
    if user_id:
        from sqlalchemy import select
        from app.models.business import User
        user = await catalog_repo.db.get(User, user_id)
        if user and user.member_level:
            member_discount_map = {"gold": Decimal("0.1"), "silver": Decimal("0.05")}
            ratio = member_discount_map.get(user.member_level, Decimal("0"))
            if ratio:
                member_discount = (original * ratio).quantize(Decimal("0.01"))

    # 优惠券折扣
    if coupon_id:
        from sqlalchemy import select
        from app.models.business import Coupon
        coupon = await catalog_repo.db.get(Coupon, coupon_id)
        if coupon and coupon.status == "unused" and coupon.discount_value:
            now = datetime.now(UTC).replace(tzinfo=None)
            if (coupon.valid_from is None or coupon.valid_from <= now) and (coupon.valid_to is None or coupon.valid_to >= now):
                if coupon.min_order_amount is None or original >= coupon.min_order_amount:
                    coupon_discount = Decimal(coupon.discount_value).quantize(Decimal("0.01"))

    final = max(original - member_discount - coupon_discount - promotion_discount, Decimal("0"))
    calculated_at = datetime.now(UTC).isoformat()

    return PriceOutput(
        original_price=original,
        member_discount=member_discount,
        coupon_discount=coupon_discount,
        promotion_discount=promotion_discount,
        final_price=final,
        price_snapshot={
            "service_id": service_id,
            "coupon_id": coupon_id,
            "calculated_at": calculated_at,
            "original_price": str(original),
            "member_discount": str(member_discount),
            "coupon_discount": str(coupon_discount),
            "final_price": str(final),
        },
    )
