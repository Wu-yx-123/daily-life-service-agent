# 作用：计算服务价格并生成价格快照，避免订单确认时价格漂移。
from datetime import UTC, datetime
from decimal import Decimal

from app.repositories.catalog_repo import CatalogRepository
from app.schemas.agent import PriceOutput


class PriceService:
    """价格计算服务。

    MVP 暂不叠加会员和优惠券，保留 price_snapshot 便于后续扩展。
    """

    def __init__(self, catalog_repo: CatalogRepository):
        self.catalog_repo = catalog_repo

    async def calculate(self, *, service_id: str, user_id: str | None = None) -> PriceOutput:
        """读取服务原价并生成确定性的价格快照。"""
        service = await self.catalog_repo.get_service(service_id)
        if not service:
            raise ValueError("service not found")
        original = Decimal(service.base_price)
        calculated_at = datetime.now(UTC).isoformat()
        return PriceOutput(
            original_price=original,
            final_price=original,
            price_snapshot={
                "service_id": service_id,
                "coupon_id": None,
                "calculated_at": calculated_at,
                "original_price": str(original),
                "final_price": str(original),
            },
        )
