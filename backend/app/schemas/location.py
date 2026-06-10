# 作用：位置解析和附近门店推荐接口的数据结构。
from pydantic import BaseModel, Field, model_validator


class LocationResolveRequest(BaseModel):
    """用户位置输入：可传经纬度，也可传文字地址。"""

    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    address: str | None = Field(default=None, min_length=1, max_length=256)
    city: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def require_coordinate_or_address(self):
        has_coordinates = self.latitude is not None and self.longitude is not None
        if not has_coordinates and not self.address:
            raise ValueError("必须提供经纬度或地址")
        return self


class ResolvedLocationResponse(BaseModel):
    """解析后的标准位置。"""

    latitude: float
    longitude: float
    formatted_address: str | None = None
    province: str | None = None
    city: str | None = None
    district: str | None = None
    source: str


class StoreRecommendation(BaseModel):
    """推荐门店。"""

    id: str
    name: str
    address: str
    latitude: float | None = None
    longitude: float | None = None
    opening_time: str
    closing_time: str
    distance_km: float | None = None
    reason: str


class StoreRecommendationRequest(LocationResolveRequest):
    """附近门店推荐请求。"""

    limit: int = Field(default=5, ge=1, le=20)


class StoreRecommendationResponse(BaseModel):
    """附近门店推荐结果。"""

    location: ResolvedLocationResponse
    stores: list[StoreRecommendation]
