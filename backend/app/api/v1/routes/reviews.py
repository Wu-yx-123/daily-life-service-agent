# 作用：提供评价分析接口，支撑 Phase 3 ReviewAgent。
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.repositories.review_repo import ReviewRepository
from app.schemas.agent import ReviewAnalyzeRequest, ReviewAnalyzeResponse
from app.services.review_service import ReviewService

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.post("/analyze", response_model=ReviewAnalyzeResponse)
async def analyze_review(payload: ReviewAnalyzeRequest, db: AsyncSession = Depends(get_db)):
    """分析评价情绪并保存评价记录。"""
    review, analysis = await ReviewService(db, ReviewRepository(db)).analyze_and_create(payload)
    return ReviewAnalyzeResponse(
        id=str(review.id),
        sentiment=analysis.sentiment,
        reason_tags=analysis.reason_tags,
        summary=analysis.summary,
    )
