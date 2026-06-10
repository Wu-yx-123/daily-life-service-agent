# 作用：人工审批接口——审批通过后自动从 resume_state 恢复流程并创建订单。
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_time_lock_store
from app.core.database import get_db
from app.core.redis import TimeLockStore
from app.harness.orchestrator import HarnessOrchestrator
from app.repositories.approval_repo import ApprovalRepository
from app.schemas.agent import (
    ApprovalDecisionRequest,
    ApprovalDecisionResponse,
    ApprovalListItem,
    CandidateOption,
    OrderDraft,
    PriceOutput,
    ScheduleOutput,
)
from app.services.order_service import OrderService
from app.repositories.order_repo import OrderRepository

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/approvals", tags=["approvals"])


def _to_item(request) -> ApprovalListItem:
    return ApprovalListItem(
        id=str(request.id), trace_id=request.trace_id, session_id=request.session_id,
        user_id=request.user_id, approval_type=request.approval_type, status=request.status,
        risk_level=request.risk_level, reason=request.reason, snapshot=request.snapshot,
        order_id=str(request.order_id) if request.order_id else None,
        reviewer_note=request.reviewer_note, created_at=request.created_at,
        reviewed_at=request.reviewed_at,
    )


def _draft_from_snapshot(snapshot: dict, user_id: str) -> OrderDraft:
    """旧版：从快照恢复草稿（无 resume_state 时回退使用）。"""
    candidate = CandidateOption.model_validate(snapshot.get("selected_option"))
    schedule = ScheduleOutput.model_validate(snapshot.get("schedule_check"))
    price = PriceOutput.model_validate(snapshot.get("price_result"))
    if not schedule.available or not schedule.room_id or not schedule.appointment_start or not schedule.appointment_end:
        raise ValueError("approval snapshot does not contain a valid schedule")
    return OrderDraft(
        user_id=user_id, option_id=candidate.option_id, store_id=candidate.store_id,
        service_id=candidate.service_id, technician_id=candidate.technician_id,
        room_id=schedule.room_id, appointment_start=schedule.appointment_start,
        appointment_end=schedule.appointment_end, original_price=price.original_price,
        final_price=price.final_price, lock_id=schedule.lock_id or "approval_rechecked",
        price_snapshot=price.price_snapshot,
    )


@router.get("", response_model=list[ApprovalListItem])
async def list_approvals(status: str | None = None, db: AsyncSession = Depends(get_db)):
    requests = await ApprovalRepository(db).list(status=status)
    return [_to_item(item) for item in requests]


@router.post("/{approval_id}/decision", response_model=ApprovalDecisionResponse)
async def decide_approval(
    approval_id: str, payload: ApprovalDecisionRequest,
    db: AsyncSession = Depends(get_db),
    lock_store: TimeLockStore = Depends(get_time_lock_store),
):
    """提交审批结果。批准时自动从 resume_state 恢复流程创建订单。"""
    repo = ApprovalRepository(db)
    request = await repo.get(approval_id)
    if not request:
        raise HTTPException(status_code=404, detail="approval request not found")
    if request.status != "pending":
        raise HTTPException(status_code=409, detail="approval request already reviewed")

    order_id: str | None = None
    status_msg = ""

    if payload.decision == "approved":
        # 优先使用 resume_state（Orchestrator.resume）恢复完整流程
        if request.resume_state and request.resume_step:
            try:
                orch = HarnessOrchestrator(db, lock_store)
                result = await orch.resume(
                    trace_id=request.trace_id,
                    session_id=request.session_id or "",
                    user_id=request.user_id,
                    resume_state=request.resume_state,
                )
                order_id = result.get("order_id")
                if order_id:
                    status_msg = "审批通过，流程自动恢复，订单已创建"
                else:
                    status_msg = f"审批通过但创建失败: {result.get('errors', [])}"
            except Exception as exc:
                status_msg = f"审批通过但恢复执行失败: {exc}"
                logger.warning("resume failed: %s", exc)

        # 回退：无 resume_state 时直接从 snapshot 重建草稿（旧版路径）
        if not order_id:
            try:
                draft = _draft_from_snapshot(request.snapshot, user_id=request.user_id)
                order = await OrderService(db, OrderRepository(db)).create_confirmed_order(
                    user_id=request.user_id, draft=draft)
                order_id = str(order.id)
                status_msg = status_msg or "审批通过，订单已创建"
            except ValueError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
    else:
        status_msg = "审批已驳回"

    await repo.decide(request, status=payload.decision, reviewer_note=payload.reviewer_note, order_id=order_id)
    await db.commit()
    return ApprovalDecisionResponse(id=str(request.id), status=request.status, message=status_msg, order_id=order_id)
