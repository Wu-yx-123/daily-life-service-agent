# 作用：服务/门店/技师查询工具，供 MatchAgent 和 IntentAgent 调用。
# 所有函数签名与 ToolRegistry.register 兼容，第一参数通过 args dict 传入。
from app.repositories.catalog_repo import CatalogRepository
from app.schemas.agent import IntentOutput, MatchOutput


async def search_services(
    *,
    catalog_repo: CatalogRepository,
    intent: dict,
    **kwargs,
) -> MatchOutput:
    """根据用户意图匹配候选服务和技师。

    ToolRegistry 调用入口。此工具会委托 MatchService 做完整的匹配逻辑。
    """
    from app.services.match_service import MatchService

    parsed = IntentOutput.model_validate(intent)
    service = MatchService(catalog_repo)
    return await service.match(parsed)


async def get_service_detail(
    *,
    catalog_repo: CatalogRepository,
    service_id: str,
    **kwargs,
) -> dict | None:
    """查询单个服务项目详情。"""
    service = await catalog_repo.get_service(service_id)
    if not service:
        return None
    return {
        "id": str(service.id),
        "store_id": str(service.store_id),
        "name": service.name,
        "category": service.category,
        "duration_minutes": service.duration_minutes,
        "base_price": str(service.base_price),
        "description": service.description,
        "tags": service.tags,
    }


async def search_technicians(
    *,
    catalog_repo: CatalogRepository,
    store_id: str | None = None,
    skill_tags: list[str] | None = None,
    **kwargs,
) -> list[dict]:
    """查询可接单技师，支持按门店和技能标签过滤。"""
    techs = await catalog_repo.list_active_technicians(store_id=store_id)
    results = []
    for tech in techs:
        if skill_tags and tech.skill_tags:
            if not any(tag in tech.skill_tags for tag in skill_tags):
                continue
        results.append({
            "id": str(tech.id),
            "store_id": str(tech.store_id),
            "name": tech.name,
            "skill_tags": tech.skill_tags,
            "rating": float(tech.rating) if tech.rating else None,
        })
    return results


async def search_stores(
    *,
    catalog_repo: CatalogRepository,
    **kwargs,
) -> list[dict]:
    """查询活跃门店列表。"""
    # CatalogRepository 没有直接 list_stores 方法，这里按需补充。
    from sqlalchemy import select
    from app.models.business import Store
    stores = list((await catalog_repo.db.scalars(
        select(Store).where(Store.status == "active")
    )).all())
    return [
        {
            "id": str(s.id),
            "name": s.name,
            "address": s.address,
            "opening_time": str(s.opening_time),
            "closing_time": str(s.closing_time),
        }
        for s in stores
    ]
