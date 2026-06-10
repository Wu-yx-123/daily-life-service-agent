# 作用：提供运营报表接口，支撑 Phase 3 OpsAgent。
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.repositories.ops_repo import OpsRepository
from app.repositories.review_repo import ReviewRepository
from app.schemas.agent import OpsReportResponse
from app.services.ops_service import OpsService

router = APIRouter(prefix="/ops", tags=["ops"])


@router.get("/report", response_model=OpsReportResponse)
async def get_ops_report(db: AsyncSession = Depends(get_db)):
    """查询经营统计和运营建议。"""
    return await OpsService(db, OpsRepository(db), ReviewRepository(db)).generate_report()
