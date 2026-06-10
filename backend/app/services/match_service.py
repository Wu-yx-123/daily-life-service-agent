# 作用：根据用户意图匹配服务项目和技师，生成预约候选方案。
from decimal import Decimal
from uuid import uuid4

from app.repositories.catalog_repo import CatalogRepository
from app.schemas.agent import CandidateOption, IntentOutput, MatchOutput
from app.utils.service_match import matches_service_type


class MatchService:
    """候选方案匹配服务。

    业务规则放在 service 中，而不是写进 prompt；Agent 只负责调用工具拿结构化结果。
    """

    def __init__(self, catalog_repo: CatalogRepository):
        self.catalog_repo = catalog_repo

    async def match(self, intent: IntentOutput) -> MatchOutput:
        """根据服务类型、时长、预算和技师技能生成候选方案。"""
        services = await self.catalog_repo.list_active_services()
        technicians = await self.catalog_repo.list_active_technicians()
        slots = intent.slots
        candidates: list[CandidateOption] = []
        for service in services:
            # 时长和预算是硬约束，先过滤能明显不匹配的服务。
            if slots.duration_minutes and service.duration_minutes != slots.duration_minutes:
                continue
            if slots.budget_max and Decimal(service.base_price) > slots.budget_max:
                continue
            service_text = " ".join([service.name, service.category or "", " ".join(service.tags or [])])
            if not matches_service_type(slots.service_type, service_text):
                continue
            # 只在服务所属门店里挑技师，避免跨门店错误匹配。
            store_techs = [tech for tech in technicians if str(tech.store_id) == str(service.store_id)]
            ranked_techs = sorted(store_techs, key=lambda tech: (self._skill_score(tech.skill_tags or [], slots.strength_preference), tech.rating or 0), reverse=True)
            for tech in ranked_techs:
                # MVP 用规则打分，后续可以替换成 hybrid search / RRF 排序。
                score = 0.75 + self._skill_score(tech.skill_tags or [], slots.strength_preference) * 0.15
                candidates.append(
                    CandidateOption(
                        option_id=f"option_{uuid4().hex[:12]}",
                        store_id=str(service.store_id),
                        service_id=str(service.id),
                        technician_id=str(tech.id),
                        service_name=service.name,
                        technician_name=tech.name,
                        base_price=service.base_price,
                        duration_minutes=service.duration_minutes,
                        match_score=round(score, 2),
                        reason=f"符合{slots.service_type or service.category or service.name}、{service.duration_minutes}分钟，技师{tech.name}评分{tech.rating}",
                    )
                )
        return MatchOutput(candidates=sorted(candidates, key=lambda item: item.match_score, reverse=True)[:6])

    @staticmethod
    def _skill_score(tags: list[str], strength: str | None) -> float:
        """计算技师技能标签与用户力度偏好的匹配度。"""
        if not strength:
            return 0.5
        if strength == "heavy" and any(tag in tags for tag in ["力度偏重", "深层放松", "肩颈"]):
            return 1.0
        return 0.5
