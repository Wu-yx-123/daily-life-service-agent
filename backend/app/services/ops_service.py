# 作用：封装运营报表生成逻辑。
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.ops_agent import OpsAgent
from app.repositories.ops_repo import OpsRepository
from app.repositories.review_repo import ReviewRepository


class OpsService:
    """运营分析服务。"""

    def __init__(self, db: AsyncSession, ops_repo: OpsRepository, review_repo: ReviewRepository, agent: OpsAgent | None = None):
        self.db = db
        self.ops_repo = ops_repo
        self.review_repo = review_repo
        self.agent = agent or OpsAgent()

    async def generate_report(self):
        """聚合经营指标并生成建议。"""
        return await self.agent.run(
            order_count=await self.ops_repo.order_count(),
            revenue_total=await self.ops_repo.revenue_total(),
            after_sales_open_count=await self.ops_repo.open_after_sales_count(),
            pending_approval_count=await self.ops_repo.pending_approval_count(),
            review_count=await self.review_repo.count(),
            average_rating=await self.review_repo.average_rating(),
            negative_review_count=await self.review_repo.count_negative(),
        )
