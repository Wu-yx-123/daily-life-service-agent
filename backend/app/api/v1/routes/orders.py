# 作用：提供用户确认预约接口，负责幂等检查、VerificationGate 终极门禁和正式订单创建。
from fastapi import APIRouter, Depends, HTTPException
import json
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_time_lock_store
from app.core.database import get_db
from app.core.redis import TimeLockStore
from app.harness.rollback import RollbackManager
from app.harness.run_store import agent_run_store
from app.harness.sandbox import TaskIsolationSandbox
from app.harness.verification import VerificationGate
from app.repositories.catalog_repo import CatalogRepository
from app.repositories.memory_repo import MemoryRepository
from app.repositories.order_repo import OrderRepository
from app.schemas.agent import OrderConfirmRequest, OrderConfirmResponse, OrderDraft, RiskOutput
from app.services.memory_service import MemoryService
from app.services.order_service import OrderService
from app.services.semantic_memory_service import SemanticMemoryService

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("/confirm", response_model=OrderConfirmResponse)
async def confirm_order(payload: OrderConfirmRequest, db: AsyncSession = Depends(get_db), lock_store: TimeLockStore = Depends(get_time_lock_store)):
    """用户确认预约——经过 VerificationGate 终极门禁。

    校验链：
    1. draft 存在 + option_id 匹配
    2. 幂等 Key 防重复点击
    3. ⚠️ VerificationGate.verify_order_creation（终极门禁）
    4. OrderService 事务层冲突复查 + 写入
    """
    raw_state = await lock_store.redis.get(TaskIsolationSandbox.agent_run_key(payload.trace_id))
    state = json.loads(raw_state) if raw_state else agent_run_store.get(payload.trace_id)
    if not state or not state.get("order_draft"):
        raise HTTPException(status_code=404, detail="order draft not found")
    draft = OrderDraft.model_validate(state["order_draft"])
    # 将用户确认标志写入草稿，供后续门禁校验
    draft.user_confirmed = payload.user_confirmed
    if payload.option_id != draft.option_id:
        raise HTTPException(status_code=400, detail="option_id does not match")
    if not payload.user_confirmed:
        await RollbackManager(lock_store).release_time_lock(draft)
        return OrderConfirmResponse(status="cancelled", message="已取消预约")

    # ── 幂等 Key ──
    idempotency_key = f"idempotency:order_confirm:{payload.trace_id}:{payload.option_id}"
    acquired = await lock_store.redis.set(idempotency_key, "1", ex=600, nx=True)
    if not acquired:
        return OrderConfirmResponse(status="duplicate", message="请勿重复提交预约确认")

    # ── VerificationGate 终极门禁 ──
    risk = RiskOutput.model_validate(state["risk_result"]) if state.get("risk_result") else None
    gate = VerificationGate(
        catalog_repo=CatalogRepository(db),
        order_repo=OrderRepository(db),
    )
    gate_result = await gate.verify_order_creation(draft=draft, risk=risk)
    if not gate_result.passed:
        await RollbackManager(lock_store).release_time_lock(draft)
        raise HTTPException(status_code=409, detail={"code": "gate_blocked", "errors": gate_result.errors})

    # ── 订单写入 ──
    try:
        order = await OrderService(db, OrderRepository(db)).create_confirmed_order(user_id=state["user_id"], draft=draft)
    except ValueError as exc:
        await RollbackManager(lock_store).release_time_lock(draft)
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    # 订单确认成功后才写长期记忆，确保用户偏好来自真实成交行为而不是临时咨询。
    await MemoryService(db, MemoryRepository(db)).record_booking_preferences(
        user_id=state["user_id"],
        state=state,
        order_id=str(order.id),
    )
    # pgvector 语义记忆是增强能力，写入失败不应该回滚已经确认的订单。
    try:
        await SemanticMemoryService(db).record_booking_memory(
            user_id=state["user_id"],
            state=state,
            order_id=str(order.id),
        )
    except Exception:
        pass
    return OrderConfirmResponse(order_id=str(order.id), status=order.status, message="预约成功")
