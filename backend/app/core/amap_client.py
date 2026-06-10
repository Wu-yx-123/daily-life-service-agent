# 作用：封装高德地图 Web 服务 API，供 LocationAgent 做地址解析和逆地理编码。
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import get_settings


class AmapClientError(RuntimeError):
    """高德 API 调用失败。"""


@dataclass(frozen=True)
class ResolvedLocation:
    """标准化后的用户位置。"""

    latitude: float
    longitude: float
    formatted_address: str | None = None
    province: str | None = None
    city: str | None = None
    district: str | None = None
    source: str = "amap"


class AmapClient:
    """高德 Web 服务 API 客户端。"""

    geocode_url = "https://restapi.amap.com/v3/geocode/geo"
    reverse_geocode_url = "https://restapi.amap.com/v3/geocode/regeo"

    def __init__(self, *, api_key: str | None = None, timeout: float | None = None) -> None:
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.amap_api_key
        self.timeout = timeout if timeout is not None else settings.amap_timeout

    def _ensure_key(self) -> None:
        if not self.api_key:
            raise AmapClientError("未配置 MASSAGEOPS_AMAP_API_KEY")

    async def geocode(self, address: str, *, city: str | None = None) -> ResolvedLocation:
        """把文字地址解析为经纬度。"""
        self._ensure_key()
        params: dict[str, Any] = {"key": self.api_key, "address": address}
        if city:
            params["city"] = city
        async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
            resp = await client.get(self.geocode_url, params=params)
        payload = resp.json()
        if payload.get("status") != "1" or not payload.get("geocodes"):
            raise AmapClientError(payload.get("info") or "高德地址解析失败")
        item = payload["geocodes"][0]
        lng, lat = [float(part) for part in item["location"].split(",", 1)]
        return ResolvedLocation(
            latitude=lat,
            longitude=lng,
            formatted_address=item.get("formatted_address") or address,
            province=item.get("province") if isinstance(item.get("province"), str) else None,
            city=item.get("city") if isinstance(item.get("city"), str) else None,
            district=item.get("district") if isinstance(item.get("district"), str) else None,
            source="amap_geocode",
        )

    async def reverse_geocode(self, *, latitude: float, longitude: float) -> ResolvedLocation:
        """把经纬度解析为地址信息。"""
        self._ensure_key()
        params = {
            "key": self.api_key,
            "location": f"{longitude},{latitude}",
            "extensions": "base",
        }
        async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as client:
            resp = await client.get(self.reverse_geocode_url, params=params)
        payload = resp.json()
        regeocode = payload.get("regeocode") or {}
        component = regeocode.get("addressComponent") or {}
        if payload.get("status") != "1" or not regeocode:
            raise AmapClientError(payload.get("info") or "高德逆地理编码失败")
        return ResolvedLocation(
            latitude=latitude,
            longitude=longitude,
            formatted_address=regeocode.get("formatted_address"),
            province=component.get("province") if isinstance(component.get("province"), str) else None,
            city=component.get("city") if isinstance(component.get("city"), str) else None,
            district=component.get("district") if isinstance(component.get("district"), str) else None,
            source="amap_reverse_geocode",
        )
