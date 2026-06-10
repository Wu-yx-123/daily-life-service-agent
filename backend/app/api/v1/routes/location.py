# 作用：位置 API——解析用户位置，并推荐附近门店。
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.location_agent import LocationAgent
from app.core.amap_client import AmapClientError
from app.core.database import get_db
from app.repositories.catalog_repo import CatalogRepository
from app.schemas.location import (
    LocationResolveRequest,
    ResolvedLocationResponse,
    StoreRecommendationRequest,
    StoreRecommendationResponse,
)

router = APIRouter(prefix="/location", tags=["location"])


@router.post("/resolve", response_model=ResolvedLocationResponse)
async def resolve_location(payload: LocationResolveRequest, db: AsyncSession = Depends(get_db)):
    """解析用户位置：支持浏览器经纬度或文字地址。"""
    try:
        return await LocationAgent(CatalogRepository(db)).resolve(payload)
    except AmapClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/recommend-stores", response_model=StoreRecommendationResponse)
async def recommend_stores(payload: StoreRecommendationRequest, db: AsyncSession = Depends(get_db)):
    """根据用户位置推荐附近门店。"""
    try:
        return await LocationAgent(CatalogRepository(db)).recommend_stores(payload)
    except AmapClientError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
