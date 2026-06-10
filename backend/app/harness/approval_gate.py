# 作用：实现人工审批闸门，把中高风险流程转为审批单，并保存完整状态用于审批通过后自动恢复。
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.approval_repo import ApprovalRepository
from app.schemas.agent import ApprovalRequestSnapshot, RiskOutput

logger = logging.getLogger(__name__)


class ApprovalGate:
    """人工审批闸门。

    创建审批单时保存完整 AgentState（resume_state + resume_step），
    管理员审批通过后 Orchestrator.resume() 可自动继续流程。
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ApprovalRepository(db)

    async def submit_if_needed(
        self,
        *,
        trace_id: str,
        session_id: str | None,
        user_id: str,
        risk: RiskOutput,
        snapshot: ApprovalRequestSnapshot,
        full_state: dict[str, Any] | None = None,
    ) -> object | None:
        """必要时创建审批单；低风险流程直接放行。

        Args:
            full_state: 完整的 AgentState，审批通过后用于 resume。
        """
        if not risk.requires_approval:
            return None
        request = await self.repo.create(
            trace_id=trace_id,
            session_id=session_id,
            user_id=user_id,
            approval_type="booking_risk_review",
            status="pending",
            risk_level=risk.risk_level,
            reason="；".join(risk.reasons) or "RiskAgent 要求人工审核",
            snapshot=snapshot.model_dump(mode="json"),
            resume_state=full_state,
            resume_step="create_order",
        )
        await self.db.commit()
        logger.info("审批单已创建: id=%s risk=%s", request.id, risk.risk_level)
        return request
