# 作用：测试 LocationAgent 的位置解析和附近门店推荐。
from datetime import time

import pytest

from app.agents.location_agent import LocationAgent, haversine_km
from app.core.amap_client import ResolvedLocation
from app.models.business import Store
from app.repositories.catalog_repo import CatalogRepository
from app.schemas.location import StoreRecommendationRequest


class FakeGeocoder:
    """测试用地理编码器，避免单元测试依赖真实高德网络。"""

    async def geocode(self, address: str, *, city: str | None = None) -> ResolvedLocation:
        return ResolvedLocation(
            latitude=31.2304,
            longitude=121.4737,
            formatted_address=address,
            city=city or "上海市",
            source="fake_geocode",
        )

    async def reverse_geocode(self, *, latitude: float, longitude: float) -> ResolvedLocation:
        return ResolvedLocation(
            latitude=latitude,
            longitude=longitude,
            formatted_address="当前位置",
            city="上海市",
            source="fake_reverse_geocode",
        )


async def test_location_agent_recommends_nearest_store(db_session):
    """LocationAgent 应按用户位置到门店的距离排序。"""
    near = Store(
        name="静心按摩 人民广场店",
        address="上海市黄浦区人民广场",
        latitude=31.2304,
        longitude=121.4737,
        opening_time=time(8, 0),
        closing_time=time(23, 59, 59),
    )
    far = Store(
        name="静心按摩 虹桥店",
        address="上海市闵行区虹桥",
        latitude=31.1967,
        longitude=121.3200,
        opening_time=time(8, 0),
        closing_time=time(23, 59, 59),
    )
    db_session.add_all([near, far])
    await db_session.commit()

    agent = LocationAgent(CatalogRepository(db_session), geocoder=FakeGeocoder())
    result = await agent.recommend_stores(StoreRecommendationRequest(latitude=31.2304, longitude=121.4737, limit=2))

    assert result.location.source == "fake_reverse_geocode"
    assert result.stores[0].name == "静心按摩 人民广场店"
    assert result.stores[0].distance_km == pytest.approx(0.0, abs=0.01)
    assert result.stores[1].distance_km is not None


async def test_location_agent_can_resolve_address(db_session):
    """没有浏览器坐标时，LocationAgent 可通过地理编码解析地址。"""
    agent = LocationAgent(CatalogRepository(db_session), geocoder=FakeGeocoder())
    result = await agent.recommend_stores(StoreRecommendationRequest(address="上海市人民广场", city="上海市", limit=1))

    assert result.location.latitude == 31.2304
    assert result.location.longitude == 121.4737
    assert result.location.source == "fake_geocode"


def test_haversine_km_returns_reasonable_distance():
    """距离公式用于门店排序，不调用第三方路线服务。"""
    distance = haversine_km(31.2304, 121.4737, 31.1967, 121.3200)

    assert 14 < distance < 16
