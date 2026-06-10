# 作用：LocationAgent 负责解析用户位置，并按距离推荐附近门店。
from math import asin, cos, radians, sin, sqrt
from typing import Protocol

from app.core.amap_client import AmapClient, ResolvedLocation
from app.repositories.catalog_repo import CatalogRepository
from app.schemas.location import (
    LocationResolveRequest,
    ResolvedLocationResponse,
    StoreRecommendation,
    StoreRecommendationRequest,
    StoreRecommendationResponse,
)


class Geocoder(Protocol):
    """地理编码器协议，方便测试时替换高德客户端。"""

    async def geocode(self, address: str, *, city: str | None = None) -> ResolvedLocation: ...
    async def reverse_geocode(self, *, latitude: float, longitude: float) -> ResolvedLocation: ...


class LocationAgent:
    """位置 Agent：定位用户，并推荐距离最近的可用门店。"""

    name = "LocationAgent"

    def __init__(self, repo: CatalogRepository, geocoder: Geocoder | None = None):
        self.repo = repo
        self.geocoder = geocoder or AmapClient()

    async def resolve(self, payload: LocationResolveRequest) -> ResolvedLocationResponse:
        """解析用户位置：经纬度优先，地址输入时调用高德地理编码。"""
        if payload.latitude is not None and payload.longitude is not None:
            try:
                resolved = await self.geocoder.reverse_geocode(latitude=payload.latitude, longitude=payload.longitude)
            except Exception:
                # 浏览器定位已经给出坐标时，逆地理编码失败不影响附近门店推荐。
                resolved = ResolvedLocation(
                    latitude=payload.latitude,
                    longitude=payload.longitude,
                    formatted_address=payload.address,
                    city=payload.city,
                    source="browser_geolocation",
                )
        else:
            resolved = await self.geocoder.geocode(payload.address or "", city=payload.city)
        return ResolvedLocationResponse(**resolved.__dict__)

    async def recommend_stores(self, payload: StoreRecommendationRequest) -> StoreRecommendationResponse:
        """根据用户位置推荐附近门店。"""
        location = await self.resolve(payload)
        stores = await self.repo.list_active_stores()
        ranked: list[StoreRecommendation] = []
        for store in stores:
            distance = None
            reason = "门店暂未配置坐标，已按营业状态展示。"
            if store.latitude is not None and store.longitude is not None:
                distance = haversine_km(location.latitude, location.longitude, store.latitude, store.longitude)
                reason = f"距离约 {distance:.1f} 公里，营业时间 {store.opening_time.strftime('%H:%M')} - {store.closing_time.strftime('%H:%M')}。"
            ranked.append(
                StoreRecommendation(
                    id=str(store.id),
                    name=store.name,
                    address=store.address,
                    latitude=store.latitude,
                    longitude=store.longitude,
                    opening_time=store.opening_time.isoformat(),
                    closing_time=store.closing_time.isoformat(),
                    distance_km=round(distance, 2) if distance is not None else None,
                    reason=reason,
                )
            )
        ranked.sort(key=lambda item: item.distance_km if item.distance_km is not None else float("inf"))
        return StoreRecommendationResponse(location=location, stores=ranked[:payload.limit])


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """用球面距离公式计算两点之间的直线距离。"""
    radius_km = 6371.0
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 2 * radius_km * asin(sqrt(a))
