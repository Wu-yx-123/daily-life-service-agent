# 作用：封装评价分析和入库逻辑。
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.review_agent import ReviewAgent
from app.repositories.review_repo import ReviewRepository
from app.schemas.agent import ReviewAnalyzeRequest


class ReviewService:
    """评价服务。

    ReviewAgent 只生成分析结果，评价入库仍由 service 层统一执行。
    """

    def __init__(self, db: AsyncSession, repo: ReviewRepository, agent: ReviewAgent | None = None):
        self.db = db
        self.repo = repo
        self.agent = agent or ReviewAgent()

    async def analyze_and_create(self, payload: ReviewAnalyzeRequest):
        """分析评价并保存 sentiment。"""
        analysis = await self.agent.run(rating=payload.rating, content=payload.content)
        review = await self.repo.create(
            order_id=payload.order_id,
            user_id=payload.user_id,
            rating=payload.rating,
            content=payload.content,
            sentiment=analysis.sentiment,
        )
        await self.db.commit()
        return review, analysis
