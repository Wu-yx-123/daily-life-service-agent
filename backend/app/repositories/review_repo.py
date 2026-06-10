# 作用：封装评价创建和统计查询。
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import Review


class ReviewRepository:
    """评价仓储。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, **data) -> Review:
        """创建评价记录。"""
        review = Review(**data)
        self.db.add(review)
        await self.db.flush()
        return review

    async def count(self) -> int:
        """统计评价数量。"""
        return int(await self.db.scalar(select(func.count()).select_from(Review)) or 0)

    async def average_rating(self) -> float | None:
        """计算平均评分。"""
        value = await self.db.scalar(select(func.avg(Review.rating)))
        return float(value) if value is not None else None

    async def count_negative(self) -> int:
        """统计负向评价数量。"""
        return int(await self.db.scalar(select(func.count()).select_from(Review).where(Review.sentiment == "negative")) or 0)
