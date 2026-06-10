# 作用：提供自然语言预约聊天接口——标准版 + SSE 流式版。
import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_time_lock_store
from app.core.database import get_db
from app.core.redis import TimeLockStore
from app.harness.orchestrator import HarnessOrchestrator
from app.schemas.agent import BookingOptionResponse, ConversationRequest, ConversationResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/conversations", tags=["conversations"])

STEP_MESSAGES = {
    "parse_intent": "正在理解预约需求…",
    "resolve_slots": "正在确认多轮预约信息…",
    "verify_intent": "正在校验预约信息…",
    "plan_task": "正在规划执行流程…",
    "match_service": "正在匹配服务和技师…",
    "check_schedule": "正在检查排班和房间…",
    "calculate_price": "正在计算价格…",
    "risk_check": "正在进行风险审核…",
    "approval_gate": "正在检查审批状态…",
    "present_options": "正在生成预约方案…",
    "customer_service": "正在处理售后请求…",
}


@router.post("/message", response_model=ConversationResponse)
async def post_message(
    payload: ConversationRequest,
    db: AsyncSession = Depends(get_db),
    lock_store: TimeLockStore = Depends(get_time_lock_store),
):
    """标准版：返回完整结果。"""
    state = await HarnessOrchestrator(db, lock_store).run(
        user_id=payload.user_id, session_id=payload.session_id, message=payload.message,
    )
    return _state_to_response(state, payload.session_id)


@router.post("/message/stream")
async def post_message_stream(
    payload: ConversationRequest,
    db: AsyncSession = Depends(get_db),
    lock_store: TimeLockStore = Depends(get_time_lock_store),
):
    """SSE 流式版：实时推送 Agent 执行进度。"""
    async def event_stream() -> AsyncGenerator[str, None]:
        orch = HarnessOrchestrator(db, lock_store)
        try:
            async for event in orch.stream_run(
                user_id=payload.user_id, session_id=payload.session_id,
                message=payload.message,
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _state_to_response(state: dict, session_id: str) -> ConversationResponse:
    options: list[BookingOptionResponse] = []
    if state.get("order_draft") and state.get("selected_option"):
        draft = state["order_draft"]
        selected = state["selected_option"]
        options.append(BookingOptionResponse(
            option_id=draft["option_id"], service_name=selected["service_name"],
            technician_name=selected["technician_name"],
            appointment_start=draft["appointment_start"], appointment_end=draft["appointment_end"],
            final_price=draft["final_price"], reason=selected["reason"],
        ))
    rt = "booking_options" if options else "followup"
    if state.get("approval_request"):
        rt = "approval_required"
    if state.get("after_sales_ticket"):
        rt = "service_ticket"
    return ConversationResponse(
        trace_id=state["trace_id"], session_id=session_id, response_type=rt,
        message=state.get("final_response") or "请补充服务类型和预约时间。",
        options=options,
    )
