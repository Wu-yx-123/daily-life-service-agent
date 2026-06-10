# 作用：Harness 编排器，连接 LangGraph、Agent、工具权限、Trace 和运行态缓存。
import json
import logging
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

def _stream_response_type(state: dict) -> str:
    if state.get("order_draft"): return "booking_options"
    if state.get("approval_request"): return "approval_required"
    if state.get("after_sales_ticket"): return "service_ticket"
    return "followup"

def _stream_options(state: dict):
    if not state.get("order_draft") or not state.get("selected_option"): return []
    d = state["order_draft"]; s = state["selected_option"]
    return [{"option_id": d["option_id"], "service_name": s["service_name"],
             "technician_name": s["technician_name"],
             "appointment_start": str(d["appointment_start"]),
             "appointment_end": str(d["appointment_end"]),
             "final_price": str(d["final_price"]), "reason": s.get("reason", "")}]


from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import build_phase1_graph
from app.agents.customer_service_agent import CustomerServiceAgent
from app.agents.intent_agent import IntentAgent
from app.agents.knowledge_agent import KnowledgeAgent
from app.agents.match_agent import MatchAgent
from app.agents.order_agent import OrderAgent
from app.agents.planner_agent import PlannerAgent
from app.agents.price_agent import PriceAgent
from app.agents.risk_agent import RiskAgent
from app.agents.schedule_agent import ScheduleAgent
from app.agents.state import AgentState
from app.core.redis import TimeLockStore
from app.harness.approval_gate import ApprovalGate
from app.harness.permission import PermissionManager
from app.harness.rollback import RollbackManager
from app.harness.run_store import agent_run_store
from app.harness.run_store import json_default
from app.harness.sandbox import AgentToolSandbox, TaskIsolationSandbox
from app.harness.slot_resolution import SlotResolutionGate
from app.harness.tool_registry import ToolRegistry
from app.harness.trace import TraceLogger
from app.harness.verification import VerificationGate
from app.repositories.after_sales_repo import AfterSalesRepository
from app.repositories.catalog_repo import CatalogRepository
from app.repositories.knowledge_repo import KnowledgeRepository
from app.repositories.order_repo import OrderRepository
from app.harness.contract import validate_output
from app.schemas.agent import (
    ApprovalRequestSnapshot,
    CandidateOption,
    CustomerServiceOutput,
    IntentOutput,
    MatchOutput,
    OrderDraft,
    PriceOutput,
    RiskOutput,
    ScheduleOutput,
)


def _build_intent_followup(intent: IntentOutput, errors: list[dict[str, Any]]) -> str:
    """根据缺失槽位和校验错误生成可执行追问，避免只回复“信息不完整”。"""
    missing = set(intent.missing_slots)
    parts: list[str] = []

    if "service_type" in missing:
        parts.append("服务类型，例如肩颈按摩、全身放松、足底反射或精油 SPA")
    if "preferred_time" in missing:
        parts.append("预约时间，例如今晚9点、明天20点")
    if "duration_minutes" in missing:
        parts.append("服务时长，例如60分钟、90分钟或120分钟")

    codes = [error.get("code", "") for error in errors]
    if "appointment_time_too_soon" in codes:
        parts.append("一个至少提前30分钟且尚未过去的预约时间")
    if "invalid_duration" in codes:
        parts.append("5-480分钟之间的服务时长")
    if "invalid_budget" in codes:
        parts.append("大于0的预算金额")
    if "service_type_not_found" in codes:
        parts.append("门店已上线的服务类型")

    if parts:
        return "当前还需要补充或调整：" + "；".join(parts) + "。"
    return "当前请求信息还不完整或不合法，请补充必要信息。"


def _merge_booking_intent_with_previous(current: IntentOutput, previous_raw: Any) -> IntentOutput:
    """多轮补槽：用户只回答“60分钟/明天8点”时，继承上一轮已确认的预约槽位。"""
    if current.task_type != "book_appointment" or not previous_raw:
        return current
    try:
        previous = IntentOutput.model_validate(previous_raw)
    except Exception:
        return current
    if previous.task_type != "book_appointment":
        return current

    merged = current.model_copy(deep=True)
    current_slots = merged.slots
    previous_slots = previous.slots
    filled: list[str] = []

    if not current_slots.service_type and previous_slots.service_type:
        current_slots.service_type = previous_slots.service_type
        filled.append("service_type")
    if not current_slots.duration_minutes and previous_slots.duration_minutes:
        current_slots.duration_minutes = previous_slots.duration_minutes
        filled.append("duration_minutes")
    if not current_slots.preferred_time and previous_slots.preferred_time:
        current_slots.preferred_time = previous_slots.preferred_time
        filled.append("preferred_time")
    if not current_slots.strength_preference and previous_slots.strength_preference:
        current_slots.strength_preference = previous_slots.strength_preference
    if not current_slots.budget_max and previous_slots.budget_max:
        current_slots.budget_max = previous_slots.budget_max
    if not current_slots.technician_preference and previous_slots.technician_preference:
        current_slots.technician_preference = previous_slots.technician_preference

    if filled:
        merged.missing_slots = [slot for slot in merged.missing_slots if slot not in filled]
        merged.confidence = min(1.0, merged.confidence + 0.05)
    return merged
from app.services.after_sales_service import AfterSalesService
from app.services.match_service import MatchService
from app.services.memory_service import MemoryService
from app.services.price_service import PriceService
from app.services.schedule_service import ScheduleService
from app.services.semantic_memory_service import SemanticMemoryService


class HarnessOrchestrator:
    """Harness 编排器。

    负责创建 trace_id、初始化 AgentState、连接工具注册表，并驱动 LangGraph 执行。
    """

    def __init__(self, db: AsyncSession, lock_store: TimeLockStore):
        self.db = db
        self.lock_store = lock_store
        self.trace_logger = TraceLogger(db)
        self.task_sandbox = TaskIsolationSandbox()
        # 仓储只负责数据库访问；业务判断放在 service，Agent 不直接碰数据库。
        catalog_repo = CatalogRepository(db)
        self.order_repo = OrderRepository(db)
        after_sales_repo = AfterSalesRepository(db)
        knowledge_repo = KnowledgeRepository(db)
        self.verification_gate = VerificationGate(
            catalog_repo=catalog_repo, order_repo=self.order_repo, after_sales_repo=after_sales_repo,
        )
        self.approval_gate_runner = ApprovalGate(db)
        self.rollback_manager = RollbackManager(lock_store)
        self.slot_resolution_gate = SlotResolutionGate()
        # 所有工具先注册到 ToolRegistry，再由 Agent 通过名字调用。
        # 这样后续扩展 RiskAgent / ApprovalGate 时，权限边界依旧清晰。
        tools = ToolRegistry(PermissionManager(), AgentToolSandbox())

        # ── Phase 1 基础工具 ──
        tools.register("search_services", MatchService(catalog_repo).match)
        tools.register("check_schedule", ScheduleService(catalog_repo, self.order_repo, lock_store).check_and_lock)
        tools.register("calculate_price", PriceService(catalog_repo).calculate)

        # ── Phase 2+ 扩展工具（服务/技师/门店查询） ──
        from app.tools.service_tools import get_service_detail as _svc_detail, search_technicians as _svc_tech, search_stores as _svc_stores
        tools.register("get_service_detail", _svc_detail)
        tools.register("search_technicians", _svc_tech)
        tools.register("search_stores", _svc_stores)

        # ── 排班与时间锁工具 ──
        from app.tools.schedule_tools import create_time_lock as _sch_lock, release_time_lock as _sch_release
        tools.register("create_time_lock", _sch_lock)
        tools.register("release_time_lock", _sch_release)

        # ── 订单工具 ──
        from app.tools.order_tools import create_order as _ord_create, get_order as _ord_get, list_user_orders as _ord_list, check_order_conflicts as _ord_conflict
        tools.register("create_order", _ord_create)
        tools.register("get_order", _ord_get)
        tools.register("list_user_orders", _ord_list)
        tools.register("check_order_conflicts", _ord_conflict)

        # ── 价格工具 ──
        from app.tools.price_tools import list_available_coupons as _pr_coupons, calculate_discounted_price as _pr_discounted
        tools.register("list_available_coupons", _pr_coupons)
        tools.register("calculate_discounted_price", _pr_discounted)

        # ── 风控工具 ──
        from app.tools.risk_tools import check_user_risk as _risk_check, create_risk_record as _risk_rec
        tools.register("check_user_risk", _risk_check)
        tools.register("create_risk_record", _risk_rec)

        # ── 搜索工具 ──
        from app.tools.search_tools import search_knowledge as _srch_know, search_services_by_keyword as _srch_svc
        tools.register("search_knowledge", _srch_know)
        tools.register("search_services_by_keyword", _srch_svc)

        # ── 通知工具 ──
        from app.tools.notification_tools import send_booking_confirmation as _notif_book, notify_admin as _notif_admin, send_after_sales_notification as _notif_as
        tools.register("send_booking_confirmation", _notif_book)
        tools.register("notify_admin", _notif_admin)
        tools.register("send_after_sales_notification", _notif_as)

        # Phase 1 使用确定性 Agent，先保证业务闭环稳定；未来可以把 IntentAgent 换成 LLM。
        self.intent_agent = IntentAgent()
        self.planner_agent = PlannerAgent()
        self.match_agent = MatchAgent(tools)
        self.schedule_agent = ScheduleAgent(tools)
        self.price_agent = PriceAgent(tools)
        self.risk_agent = RiskAgent()
        self.customer_service_agent = CustomerServiceAgent()
        self.knowledge_agent = KnowledgeAgent(knowledge_repo)
        self.after_sales_service = AfterSalesService(db, after_sales_repo)
        self.memory_service = MemoryService(db)
        self.semantic_memory_service = SemanticMemoryService(db)
        self.order_agent = OrderAgent()
        self.graph = build_phase1_graph(
            {
                "parse_intent": self.parse_intent,
                "resolve_slots": self.resolve_slots,
                "verify_intent": self.verify_intent,
                "plan_task": self.plan_task,
                "match_service": self.match_service,
                "check_schedule": self.check_schedule,
                "calculate_price": self.calculate_price,
                "risk_check": self.risk_check,
                "approval_gate": self.approval_gate,
                "present_options": self.present_options,
                "customer_service": self.customer_service,
            }
        )

    async def run(self, *, user_id: str, session_id: str, message: str) -> AgentState:
        """执行一次用户消息对应的 Agent 工作流，带多轮对话记忆。

        每次执行：
        1. 从 SessionStore 加载上次的 AgentState 和消息历史
        2. 合并上下文（保留 selected_option / task_type 等）
        3. 执行 LangGraph
        4. 保存消息历史和最新状态
        """
        trace_id = f"trace_{uuid4().hex[:16]}"

        # ── 加载会话记忆 ──
        from app.core.session_store import get_session_store
        try:
            session_store = get_session_store(self.lock_store.redis)
            last_state = await session_store.get_last_state(session_id)
            history = await session_store.recent_messages(session_id, n=10)
        except Exception:
            last_state = None
            history = []
        # ── 加载长期记忆 ──
        # 长期记忆来自 PostgreSQL，用于服务/力度/预算等稳定偏好的召回。
        # 失败时降级为空画像，不影响当前预约主链路。
        try:
            long_term_memory = await self.memory_service.retrieve_for_user(user_id=user_id)
        except Exception:
            long_term_memory = {"preferences": {}, "defaults": {}}
        # ── 加载语义长期记忆 ──
        # pgvector 按当前消息做相似度召回，保存的是用户私有的自然语言经验。
        try:
            semantic_memories = await self.semantic_memory_service.retrieve_for_user(
                user_id=user_id,
                query=message,
            )
        except Exception:
            semantic_memories = []
        long_term_memory["semantic_memories"] = semantic_memories

        # 构建初始状态，合并上一轮的上下文
        state: AgentState = {
            "trace_id": trace_id,
            "session_id": session_id,
            "user_id": user_id,
            "user_message": message,
            "conversation_history": history,
            # AgentState 中同时保留短期历史和长期画像，便于 Trace 解释本轮推理依据。
            "long_term_memory": long_term_memory,
            "semantic_memories": semantic_memories,
            "errors": [],
        }
        # 跨轮保留：候选方案、任务类型等，用于理解"换成明天同一时间"
        if last_state:
            if last_state.get("intent") is not None:
                state["previous_intent"] = last_state["intent"]
            for key in ("selected_option", "candidates", "task_type", "order_draft",
                        "schedule_check", "price_result", "intent"):
                if key in last_state and last_state[key] is not None:
                    state[key] = last_state[key]  # type: ignore[literal-required]

        async with self.task_sandbox.context(trace_id=trace_id, session_id=session_id, user_id=user_id):
            result = await self.graph.ainvoke(state)
            self.task_sandbox.ensure_state_belongs_to_current_task(result)

            # ── 保存会话记忆 ──
            try:
                await session_store.append_message(session_id, "user", message)
                final_text = result.get("final_response", "")
                if final_text:
                    await session_store.append_message(session_id, "assistant", final_text)
                await session_store.save_state(session_id, result)
            except Exception:
                pass  # 会话存储不是关键路径，失败不影响业务

            # 进程内缓存 + Redis
            agent_run_store.save(trace_id, result)
            await self.lock_store.redis.set(
                self.task_sandbox.agent_run_key(trace_id),
                json.dumps(result, default=json_default), ex=1800,
            )
            return result

    async def resume(self, *, trace_id: str, session_id: str, user_id: str, resume_state: dict) -> dict[str, Any]:
        """审批通过后从保存的状态恢复流程，执行 create_order 步骤。

        返回 {"order_id": str | None, "status": str, "errors": list}
        """
        from app.services.order_service import OrderService
        from app.schemas.agent import CandidateOption, PriceOutput, ScheduleOutput

        new_trace = f"trace_{uuid4().hex[:16]}"
        async with self.task_sandbox.context(trace_id=new_trace, session_id=session_id, user_id=user_id):
            try:
                candidate = CandidateOption.model_validate(resume_state["selected_option"])
                original_sched = ScheduleOutput.model_validate(resume_state["schedule_check"])
                price = PriceOutput.model_validate(resume_state["price_result"])
                intent = IntentOutput.model_validate(resume_state["intent"])

                # 审批期间不长期占用 Redis 时间锁；通过后必须重新排班并获取新锁。
                async def recheck_schedule_step():
                    output = await self.schedule_agent.run(
                        candidate=candidate,
                        intent=intent,
                        user_id=user_id,
                        trace_id=new_trace,
                    )
                    return output.model_dump(mode="json")

                sched_raw = await self.trace_logger.traced(
                    trace_id=new_trace,
                    session_id=session_id,
                    agent_name="ScheduleAgent",
                    step_name="approval_recheck_schedule",
                    input={
                        "original_trace": trace_id,
                        "candidate": candidate.model_dump(mode="json"),
                        "previous_schedule": original_sched.model_dump(mode="json"),
                    },
                    fn=recheck_schedule_step,
                )
                sched = validate_output(sched_raw, ScheduleOutput, agent_name="ScheduleAgent")

                async def verify_schedule_step():
                    verification = await self.verification_gate.verify_schedule(
                        candidate=candidate,
                        intent=intent,
                        schedule=sched,
                    )
                    return verification.model_dump(mode="json")

                schedule_gate = await self.trace_logger.traced(
                    trace_id=new_trace,
                    session_id=session_id,
                    agent_name="VerificationGate",
                    step_name="approval_verify_schedule",
                    input=sched_raw,
                    fn=verify_schedule_step,
                )
                if not schedule_gate["passed"]:
                    if sched.available:
                        await self.rollback_manager.release_schedule_lock(candidate=candidate, schedule=sched)
                    return {
                        "order_id": None,
                        "status": "schedule_unavailable",
                        "errors": schedule_gate["errors"],
                    }

                resumed_state = dict(resume_state)
                resumed_state["schedule_check"] = sched_raw

                # 重新生成订单草稿，审批通过即视为用户已确认
                draft = await self.order_agent.draft(candidate=candidate, schedule=sched, price=price, user_id=user_id)
                draft.user_confirmed = True

                # 终极门禁
                gate_result = await self.verification_gate.verify_order_creation(draft=draft, risk=None)

                if not gate_result.passed:
                    await self.rollback_manager.release_time_lock(draft)
                    return {"order_id": None, "status": "gate_blocked", "errors": gate_result.errors}

                # 创建订单
                try:
                    order = await OrderService(self.db, OrderRepository(self.db)).create_confirmed_order(
                        user_id=user_id, draft=draft,
                    )
                except ValueError as exc:
                    await self.rollback_manager.release_time_lock(draft)
                    return {"order_id": None, "status": "order_conflict", "errors": [str(exc)]}
                # 审批通过后恢复创建订单，也要同步沉淀长期记忆，保持人工审批路径和普通确认路径一致。
                await self.memory_service.record_booking_preferences(
                    user_id=user_id,
                    state=resumed_state,
                    order_id=str(order.id),
                )
                try:
                    await self.semantic_memory_service.record_booking_memory(
                        user_id=user_id,
                        state=resumed_state,
                        order_id=str(order.id),
                    )
                except Exception:
                    pass

                # Trace 记录恢复步骤
                async def _trace_resume():
                    return {"order_id": str(order.id), "status": order.status}
                await self.trace_logger.traced(
                    trace_id=new_trace, session_id=session_id,
                    agent_name="Orchestrator", step_name="approval_resumed",
                    input={"original_trace": trace_id, "resume_step": "create_order"},
                    fn=_trace_resume,
                )

                return {"order_id": str(order.id), "status": order.status, "errors": []}
            except Exception as exc:
                logger.error("审批恢复执行失败: %s", exc)
                return {"order_id": None, "status": "resume_failed", "errors": [str(exc)]}

    async def stream_run(self, *, user_id: str, session_id: str, message: str):
        """SSE 流式执行——直接调用 Agent（绕过 TraceLogger），实时推送进度。"""
        from app.core.session_store import get_session_store

        trace_id = f"trace_{uuid4().hex[:16]}"
        try:
            session_store = get_session_store(self.lock_store.redis)
            last_state = await session_store.get_last_state(session_id)
            history = await session_store.recent_messages(session_id, n=10)
        except Exception:
            last_state = None; history = []
        # SSE 流式路径和标准 run 路径都要加载长期记忆，保证两种 API 行为一致。
        try:
            long_term_memory = await self.memory_service.retrieve_for_user(user_id=user_id)
        except Exception:
            long_term_memory = {"preferences": {}, "defaults": {}}
        # SSE 流式路径也召回 pgvector 语义记忆，避免流式和非流式结果不一致。
        try:
            semantic_memories = await self.semantic_memory_service.retrieve_for_user(
                user_id=user_id,
                query=message,
            )
        except Exception:
            semantic_memories = []
        long_term_memory["semantic_memories"] = semantic_memories

        state: AgentState = {"trace_id": trace_id, "session_id": session_id,
                             "user_id": user_id, "user_message": message,
                             "conversation_history": history,
                             "long_term_memory": long_term_memory,
                             "semantic_memories": semantic_memories, "errors": []}
        if last_state:
            if last_state.get("intent") is not None:
                state["previous_intent"] = last_state["intent"]
            for key in ("selected_option", "candidates", "task_type", "order_draft",
                        "schedule_check", "price_result", "intent"):
                if key in last_state and last_state[key] is not None:
                    state[key] = last_state[key]

        yield {"type": "trace_created", "trace_id": trace_id}
        async with self.task_sandbox.context(trace_id=trace_id, session_id=session_id, user_id=user_id):
            # Step 1: IntentAgent
            yield {"type": "step_started", "step": "parse_intent", "agent": "IntentAgent", "message": "正在理解预约需求…"}
            try:
                history_list = state.get("conversation_history", [])
                intent_out = await self.intent_agent.run(
                    state["user_message"],
                    history=history_list,
                    memory_context=state.get("long_term_memory"),
                )
                intent_out = _merge_booking_intent_with_previous(intent_out, state.get("intent"))
                # LLM 输出后再做确定性补全，确保不会让模型自由决定哪些记忆可以覆盖本轮输入。
                intent_out = self.memory_service.apply_to_intent(intent_out, state.get("long_term_memory"))
                state["intent"] = intent_out.model_dump(mode="json")
                state["task_type"] = intent_out.task_type
                yield {"type": "step_finished", "step": "parse_intent", "agent": "IntentAgent", "status": "success"}
            except Exception as exc:
                yield {"type": "step_finished", "step": "parse_intent", "agent": "IntentAgent", "status": "error", "error": str(exc)}

            # Step 2: SlotResolutionGate
            yield {"type": "step_started", "step": "resolve_slots", "agent": "SlotResolutionGate", "message": "正在确认多轮预约信息…"}
            try:
                current_intent = IntentOutput.model_validate(state["intent"])
                resolved = self.slot_resolution_gate.resolve(
                    current=current_intent,
                    previous_raw=state.get("previous_intent"),
                    message=state["user_message"],
                )
                state["intent"] = resolved["intent"].model_dump(mode="json")
                state["task_type"] = resolved["intent"].task_type
                state["slot_resolution"] = resolved["slot_resolution"]
                invalidated = resolved.get("invalidated_state_keys", [])
                if "schedule_check" in invalidated or "order_draft" in invalidated:
                    await self._release_stale_schedule_lock(state)
                for key in invalidated:
                    state[key] = None
                if resolved.get("requires_confirmation"):
                    state["errors"] = state.get("errors", []) + [{
                        "code": "slot_conflict",
                        "details": resolved["slot_resolution"].get("conflicts", []),
                    }]
                    state["final_response"] = resolved.get("confirmation_question") or "请确认本次预约信息。"
                yield {"type": "step_finished", "step": "resolve_slots", "agent": "SlotResolutionGate", "status": "success"}
            except Exception as exc:
                yield {"type": "step_finished", "step": "resolve_slots", "agent": "SlotResolutionGate", "status": "error", "error": str(exc)}

            # Step 3: VerificationGate
            intent = IntentOutput.model_validate(state["intent"])
            yield {"type": "step_started", "step": "verify_intent", "agent": "VerificationGate", "message": "正在校验预约信息…"}
            try:
                if not state.get("errors"):
                    verif = await self.verification_gate.verify_intent(intent)
                    state["verification"] = verif.model_dump(mode="json")
                    if not verif.passed:
                        state["errors"] = verif.errors
                        state["final_response"] = _build_intent_followup(intent, verif.errors)
                    else:
                        state["errors"] = []
                yield {"type": "step_finished", "step": "verify_intent", "agent": "VerificationGate", "status": "success"}
            except Exception as exc:
                yield {"type": "step_finished", "step": "verify_intent", "agent": "VerificationGate", "status": "error", "error": str(exc)}

            # Step 4: PlannerAgent
            task_type = state.get("task_type", "")
            yield {"type": "step_started", "step": "plan_task", "agent": "PlannerAgent", "message": "正在规划执行流程…"}
            try:
                plan = await self.planner_agent.run(task_type)
                state["plan"] = plan
                if task_type == "service_query":
                    state["final_response"] = "我们的服务项目包括：肩颈舒缓按摩、全身放松、精油SPA、泰式按摩、足部养护、头部理疗等。"
                elif task_type == "store_query":
                    state["final_response"] = "门店位于 Tokyo，营业时间 10:00-23:00。"
                elif task_type == "unknown":
                    state["final_response"] = "抱歉，我没能理解您的需求。您可以尝试预约服务、咨询售后或了解服务项目。"
                yield {"type": "step_finished", "step": "plan_task", "agent": "PlannerAgent", "status": "success"}
            except Exception as exc:
                yield {"type": "step_finished", "step": "plan_task", "agent": "PlannerAgent", "status": "error", "error": str(exc)}

            # 分发后续
            is_booking = task_type == "book_appointment" and not state.get("errors")
            is_cs = task_type in {"cancel_order", "reschedule_order", "refund_request", "complaint"} and not state.get("errors")

            if is_booking:
                async for ev in self._stream_booking_direct(state): yield ev
            elif is_cs:
                async for ev in self._stream_cs_direct(state): yield ev

            # 保存会话
            try:
                await session_store.append_message(session_id, "user", message)
                final = state.get("final_response", "")
                if final: await session_store.append_message(session_id, "assistant", final)
                await session_store.save_state(session_id, state)
            except Exception: pass

            # SSE 路径也必须保存完整运行态，确认预约接口会用 trace_id 读取 order_draft。
            agent_run_store.save(trace_id, state)
            await self.lock_store.redis.set(
                self.task_sandbox.agent_run_key(trace_id),
                json.dumps(state, default=json_default),
                ex=1800,
            )

            yield {"type": "final", "data": {
                "trace_id": state.get("trace_id", trace_id),
                "response_type": _stream_response_type(state),
                "message": state.get("final_response", ""),
                "options": _stream_options(state),
            }}

    async def _stream_booking_steps_old_unused(self, state):
        booking_steps = [
            ("match_service", self.match_service, "MatchAgent", "正在匹配服务和技师…"),
            ("check_schedule", self.check_schedule, "ScheduleAgent", "正在检查排班和房间…"),
            ("calculate_price", self.calculate_price, "PriceAgent", "正在计算价格…"),
            ("risk_check", self.risk_check, "RiskAgent", "正在进行风险审核…"),
            ("approval_gate", self.approval_gate, "ApprovalGate", "正在检查审批状态…"),
            ("present_options", self.present_options, "OrderAgent", "正在生成预约方案…"),
        ]
        for step_name, node_fn, agent_name, msg in booking_steps:
            yield {"type": "step_started", "step": step_name, "agent": agent_name, "message": msg}
            try:
                state.update(await node_fn(state))
                yield {"type": "step_finished", "step": step_name, "agent": agent_name, "status": "success"}
            except Exception as exc:
                yield {"type": "step_finished", "step": step_name, "agent": agent_name, "status": "error", "error": str(exc)}

    async def _stream_cs_step_old_unused(self, state):
        yield {"type": "step_started", "step": "customer_service", "agent": "CustomerServiceAgent", "message": "正在处理售后请求…"}
        try:
            state.update(await self.customer_service(state))
            yield {"type": "step_finished", "step": "customer_service", "agent": "CustomerServiceAgent", "status": "success"}
        except Exception as exc:
            yield {"type": "step_finished", "step": "customer_service", "agent": "CustomerServiceAgent", "status": "error", "error": str(exc)}


    async def _stream_booking_direct(self, state):
        steps = [
            ("match_service", "MatchAgent", "正在匹配服务和技师…"),
            ("check_schedule", "ScheduleAgent", "正在检查排班和房间…"),
            ("calculate_price", "PriceAgent", "正在计算价格…"),
            ("risk_check", "RiskAgent", "正在进行风险审核…"),
            ("approval_gate", "ApprovalGate", "正在检查审批状态…"),
            ("present_options", "OrderAgent", "正在生成预约方案…"),
        ]
        for step_name, agent_name, msg in steps:
            # 前一步有错误则跳过后续步骤（与 LangGraph 条件路由一致）
            if state.get("errors") and step_name not in ("match_service",):
                yield {"type": "step_finished", "step": step_name, "agent": agent_name, "status": "skipped"}
                continue
            yield {"type": "step_started", "step": step_name, "agent": agent_name, "message": msg}
            try:
                state.update(await getattr(self, step_name)(state))
                yield {"type": "step_finished", "step": step_name, "agent": agent_name, "status": "success"}
            except Exception as exc:
                yield {"type": "step_finished", "step": step_name, "agent": agent_name, "status": "error", "error": str(exc)}

    async def _stream_cs_direct(self, state):
        yield {"type": "step_started", "step": "customer_service", "agent": "CustomerServiceAgent", "message": "正在处理售后请求…"}
        try:
            state.update(await self.customer_service(state))
            yield {"type": "step_finished", "step": "customer_service", "agent": "CustomerServiceAgent", "status": "success"}
        except Exception as exc:
            yield {"type": "step_finished", "step": "customer_service", "agent": "CustomerServiceAgent", "status": "error", "error": str(exc)}

    async def parse_intent(self, state: AgentState) -> AgentState:
        """LangGraph 节点：调用 IntentAgent，注入对话历史。

        多轮对话中，LLM 能看到前几轮的消息，理解"换成明天同一时间"这类指代。
        """
        async def step():
            history = state.get("conversation_history", [])
            output = await self.intent_agent.run(
                state["user_message"],
                history=history,
                memory_context=state.get("long_term_memory"),
            )
            output = _merge_booking_intent_with_previous(output, state.get("intent"))
            # 只用强偏好补全安全槽位；预约时间仍必须来自用户本轮输入或后续追问。
            output = self.memory_service.apply_to_intent(output, state.get("long_term_memory"))
            return output.model_dump(mode="json")

        output = await self.trace_logger.traced(
            trace_id=state["trace_id"],
            session_id=state.get("session_id"),
            agent_name="IntentAgent",
            step_name="parse_intent",
            input={"message": state["user_message"], "history_len": len(state.get("conversation_history", []))},
            fn=step,
        )
        # Contract 校验：阻止 LLM 漂移
        valid = validate_output(output, IntentOutput, agent_name="IntentAgent")
        return {"intent": valid.model_dump(mode="json"), "task_type": valid.task_type}

    async def resolve_slots(self, state: AgentState) -> AgentState:
        """LangGraph 节点：消解多轮槽位冲突，并使受影响的下游状态失效。"""
        current = IntentOutput.model_validate(state["intent"])

        async def step():
            result = self.slot_resolution_gate.resolve(
                current=current,
                previous_raw=state.get("previous_intent"),
                message=state["user_message"],
            )
            intent = result["intent"]
            return {
                "intent": intent.model_dump(mode="json"),
                "slot_resolution": result["slot_resolution"],
                "requires_confirmation": result["requires_confirmation"],
                "confirmation_question": result["confirmation_question"],
                "invalidated_state_keys": result["invalidated_state_keys"],
            }

        output = await self.trace_logger.traced(
            trace_id=state["trace_id"],
            session_id=state.get("session_id"),
            agent_name="SlotResolutionGate",
            step_name="resolve_slots",
            input={
                "message": state["user_message"],
                "intent": state["intent"],
                "previous_intent": state.get("previous_intent"),
            },
            fn=step,
        )

        invalidated = output.get("invalidated_state_keys", [])
        if "schedule_check" in invalidated or "order_draft" in invalidated:
            await self._release_stale_schedule_lock(state)

        updates: dict[str, Any] = {
            "intent": output["intent"],
            "task_type": output["intent"]["task_type"],
            "slot_resolution": output["slot_resolution"],
        }
        for key in invalidated:
            updates[key] = None

        if output.get("requires_confirmation"):
            updates["errors"] = state.get("errors", []) + [{
                "code": "slot_conflict",
                "details": output["slot_resolution"].get("conflicts", []),
            }]
            updates["final_response"] = output.get("confirmation_question") or "请确认本次预约信息。"
        return updates

    async def _release_stale_schedule_lock(self, state: AgentState) -> None:
        """槽位变化导致旧排班失效时，释放上一轮占用的时间锁。"""
        try:
            candidate = CandidateOption.model_validate(state["selected_option"]) if state.get("selected_option") else None
            schedule = ScheduleOutput.model_validate(state["schedule_check"]) if state.get("schedule_check") else None
            await self.rollback_manager.release_schedule_lock(candidate=candidate, schedule=schedule)
            return
        except Exception:
            pass
        try:
            draft = OrderDraft.model_validate(state["order_draft"]) if state.get("order_draft") else None
            await self.rollback_manager.release_time_lock(draft)
        except Exception:
            pass

    async def verify_intent(self, state: AgentState) -> AgentState:
        """LangGraph 节点：执行 Verification Gate，拦截非法或缺槽位意图。"""
        intent = IntentOutput.model_validate(state["intent"])

        async def step():
            output = await self.verification_gate.verify_intent(intent)
            return output.model_dump(mode="json")

        output = await self.trace_logger.traced(
            trace_id=state["trace_id"],
            session_id=state.get("session_id"),
            agent_name="VerificationGate",
            step_name="verify_intent",
            input=state["intent"],
            fn=step,
        )
        if not output["passed"]:
            followup = _build_intent_followup(intent, output["errors"])
            return {"verification": output, "errors": output["errors"], "final_response": followup}
        return {"verification": output, "errors": []}

    async def plan_task(self, state: AgentState) -> AgentState:
        """LangGraph 节点：根据任务类型生成执行计划。

        非预约/售后的任务（service_query / store_query / ops_analysis）在这里直接生成回复。
        """
        task_type = state["task_type"]

        async def step():
            plan = await self.planner_agent.run(task_type)
            return {"plan": plan}

        output = await self.trace_logger.traced(
            trace_id=state["trace_id"], session_id=state.get("session_id"), agent_name="PlannerAgent", step_name="plan_task", input={"task_type": task_type}, fn=step
        )
        result: dict = {"plan": output["plan"]}

        # 对非预约/非售后任务，生成即时回复
        if task_type == "service_query":
            result["final_response"] = "我们的服务项目包括：肩颈舒缓按摩、全身放松、精油SPA、泰式按摩、足部养护、头部理疗等。请问您想了解哪个项目的详情？"
        elif task_type == "store_query":
            result["final_response"] = "门店位于 Tokyo，营业时间 10:00-23:00，环境干净卫生，所有技师持证上岗。欢迎预约体验！"
        elif task_type == "ops_analysis":
            result["final_response"] = "运营分析功能请前往管理后台查看报表。"
        elif task_type == "unknown":
            result["final_response"] = "抱歉，我没能理解您的需求。您可以尝试：\n1. 预约服务（如\"今晚8点想做个肩颈按摩\"）\n2. 咨询售后（如\"我想取消预约\"）\n3. 了解服务项目（如\"有哪些按摩项目\"）"
        return result

    async def match_service(self, state: AgentState) -> AgentState:
        """LangGraph 节点：根据结构化意图匹配服务和技师。"""
        intent = IntentOutput.model_validate(state["intent"])

        async def step():
            output = await self.match_agent.run(intent)
            return output.model_dump(mode="json")

        output = await self.trace_logger.traced(
            trace_id=state["trace_id"], session_id=state.get("session_id"), agent_name="MatchAgent", step_name="match_service", input=state["intent"], fn=step
        )
        match = validate_output(output, MatchOutput, agent_name="MatchAgent")

        if not output["candidates"]:
            return {
                "candidates": [],
                "errors": state.get("errors", []) + [{"code": "no_candidates"}],
                "final_response": "暂未找到符合条件的服务或技师，请尝试调整服务类型、时长、时间或预算。",
            }

        async def verify_step():
            verification = await self.verification_gate.verify_candidates(intent=intent, match=match)
            return verification.model_dump(mode="json")

        verification = await self.trace_logger.traced(
            trace_id=state["trace_id"],
            session_id=state.get("session_id"),
            agent_name="VerificationGate",
            step_name="verify_candidates",
            input=output,
            fn=verify_step,
        )
        if not verification["passed"]:
            return {"candidates": output["candidates"], "errors": state.get("errors", []) + verification["errors"],
                    "final_response": "当前候选方案存在数据异常，请稍后重试或联系管理员。"}
        return {"candidates": output["candidates"], "selected_option": output["candidates"][0]}

    async def check_schedule(self, state: AgentState) -> AgentState:
        """LangGraph 节点：校验排班并写入 Redis 临时时间锁。"""
        if not state.get("selected_option"):
            return {}
        intent = IntentOutput.model_validate(state["intent"])
        candidates_raw = state.get("candidates") or [state["selected_option"]]
        candidates = [CandidateOption.model_validate(item) for item in candidates_raw]
        last_output: dict[str, Any] | None = None
        collected_errors: list[dict[str, Any]] = []

        for candidate in candidates:
            async def step(candidate: CandidateOption = candidate):
                output = await self.schedule_agent.run(candidate=candidate, intent=intent, user_id=state["user_id"], trace_id=state["trace_id"])
                return output.model_dump(mode="json")

            output = await self.trace_logger.traced(
                trace_id=state["trace_id"],
                session_id=state.get("session_id"),
                agent_name="ScheduleAgent",
                step_name="check_schedule",
                input=candidate.model_dump(mode="json"),
                fn=step,
            )
            last_output = output
            schedule = validate_output(output, ScheduleOutput, agent_name="ScheduleAgent")

            async def verify_step(candidate: CandidateOption = candidate, schedule: ScheduleOutput = schedule):
                verification = await self.verification_gate.verify_schedule(candidate=candidate, intent=intent, schedule=schedule)
                return verification.model_dump(mode="json")

            verification = await self.trace_logger.traced(
                trace_id=state["trace_id"],
                session_id=state.get("session_id"),
                agent_name="VerificationGate",
                step_name="verify_schedule",
                input=output,
                fn=verify_step,
            )
            if verification["passed"]:
                return {"selected_option": candidate.model_dump(mode="json"), "schedule_check": output}
            collected_errors.extend(verification["errors"])
            if schedule.available:
                await self.rollback_manager.release_schedule_lock(candidate=candidate, schedule=schedule)

        # 所有候选技师/房间都不可用时才追问换时间。
        alt_msg = "当前时段暂无可用技师或房间。"
        if intent.slots.preferred_time:
            from datetime import timedelta
            alt_time = intent.slots.preferred_time + timedelta(hours=1)
            alt_msg += f" 建议尝试 {alt_time.strftime('%m月%d日 %H:%M')} 或稍晚时段。"
        return {
            "schedule_check": last_output or {},
            "errors": state.get("errors", []) + collected_errors,
            "final_response": alt_msg,
        }

    async def calculate_price(self, state: AgentState) -> AgentState:
        """LangGraph 节点：对选中候选方案计算价格。"""
        if state.get("errors"):
            return {}
        # 价格计算只依赖 service_id 和 user_id，不信任前端传回的价格。

        async def step():
            output = await self.price_agent.run(service_id=state["selected_option"]["service_id"], user_id=state["user_id"])
            return output.model_dump(mode="json")

        output = await self.trace_logger.traced(
            trace_id=state["trace_id"], session_id=state.get("session_id"), agent_name="PriceAgent", step_name="calculate_price", input=state["selected_option"], fn=step
        )
        candidate = CandidateOption.model_validate(state["selected_option"])
        price = validate_output(output, PriceOutput, agent_name="PriceAgent")

        async def verify_step():
            verification = await self.verification_gate.verify_price(candidate=candidate, price=price)
            return verification.model_dump(mode="json")

        verification = await self.trace_logger.traced(
            trace_id=state["trace_id"],
            session_id=state.get("session_id"),
            agent_name="VerificationGate",
            step_name="verify_price",
            input=output,
            fn=verify_step,
        )
        if not verification["passed"]:
            return {"price_result": output, "errors": state.get("errors", []) + verification["errors"]}
        return {"price_result": output}

    async def risk_check(self, state: AgentState) -> AgentState:
        """LangGraph 节点：调用 RiskAgent 判断是否需要人工审批。

        注入知识库风控政策和用户历史行为数据，让风险评估更全面。
        """
        if state.get("errors") or not state.get("price_result"):
            return {}
        intent = IntentOutput.model_validate(state["intent"])
        price = PriceOutput.model_validate(state["price_result"])

        async def step():
            # 1. 查询风控政策
            knowledge_context: str | None = None
            try:
                from app.tools.search_tools import search_knowledge
                result = await search_knowledge(
                    knowledge_repo=self.knowledge_agent.repo,
                    query="风控规则 高风险订单 人工审核标准",
                )
                if result.get("hits"):
                    knowledge_context = "\n".join(
                        f"{h['title']}: {h['content']}" for h in result["hits"][:2]
                    )
            except Exception:
                pass

            # 2. 查询用户历史
            user_history: dict | None = None
            try:
                from app.tools.risk_tools import check_user_risk
                user_history = await check_user_risk(order_repo=self.order_repo, user_id=state["user_id"])
            except Exception:
                pass

            # 3. 查询技师风险
            tech_history: dict | None = None
            selected = state.get("selected_option", {})
            tech_id = selected.get("technician_id", "")
            if tech_id:
                try:
                    from app.tools.risk_tools import check_technician_risk
                    tech_history = await check_technician_risk(order_repo=self.order_repo, technician_id=tech_id)
                except Exception:
                    pass

            # 4. 价格异常检测
            price_check: dict | None = None
            try:
                from app.tools.risk_tools import check_price_anomaly
                price_check = await check_price_anomaly(
                    order_repo=self.order_repo, service_id=price.price_snapshot.get("service_id", ""),
                    final_price=float(price.final_price),
                )
            except Exception:
                pass

            # 5. RiskAgent 6 维综合判断
            output = await self.risk_agent.run(
                user_message=state["user_message"],
                intent=intent,
                price=price,
                knowledge_context=knowledge_context,
                user_history=user_history,
                tech_history=tech_history,
                price_check=price_check,
            )
            raw = output.model_dump(mode="json") if not isinstance(output, dict) else output
            return raw

        output = await self.trace_logger.traced(
            trace_id=state["trace_id"],
            session_id=state.get("session_id"),
            agent_name="RiskAgent",
            step_name="risk_check",
            input={"message": state["user_message"], "price_result": state["price_result"]},
            fn=step,
        )
        valid = validate_output(output, RiskOutput, agent_name="RiskAgent")
        # 风控结果门禁
        risk_check = await self.verification_gate.verify_risk_result(valid)
        if not risk_check.passed:
            # 风控输出异常 → 降级为 medium + 审批
            logger.warning("RiskAgent 输出校验失败: %s", risk_check.errors)
            valid = RiskOutput(risk_level="medium", reasons=["风控评估异常，进入人工审核"], requires_approval=True)
        return {"risk_result": valid.model_dump(mode="json")}

    async def approval_gate(self, state: AgentState) -> AgentState:
        """LangGraph 节点：中高风险流程进入人工审批，低风险流程直接放行。"""
        if state.get("errors") or not state.get("risk_result"):
            return {}
        risk = RiskOutput.model_validate(state["risk_result"])
        snapshot = ApprovalRequestSnapshot(
            user_message=state["user_message"],
            intent=state.get("intent"),
            selected_option=state.get("selected_option"),
            schedule_check=state.get("schedule_check"),
            price_result=state.get("price_result"),
            risk_result=state.get("risk_result"),
        )

        async def step():
            request = await self.approval_gate_runner.submit_if_needed(
                trace_id=state["trace_id"],
                session_id=state.get("session_id"),
                user_id=state["user_id"],
                risk=risk,
                snapshot=snapshot,
                full_state=state,
            )
            if not request:
                return {"requires_approval": False}
            candidate = CandidateOption.model_validate(state["selected_option"]) if state.get("selected_option") else None
            schedule = ScheduleOutput.model_validate(state["schedule_check"]) if state.get("schedule_check") else None
            await self.rollback_manager.release_schedule_lock(candidate=candidate, schedule=schedule)
            return {"requires_approval": True, "approval_id": str(request.id), "status": request.status}

        output = await self.trace_logger.traced(
            trace_id=state["trace_id"],
            session_id=state.get("session_id"),
            agent_name="ApprovalGate",
            step_name="approval_gate",
            input=state["risk_result"],
            fn=step,
        )
        if output.get("requires_approval"):
            return {
                "approval_request": output,
                "final_response": "该预约触发风险审核，已提交人工审批。管理员处理后会继续跟进。",
            }
        return {"approval_request": None}

    async def present_options(self, state: AgentState) -> AgentState:
        """LangGraph 节点：生成待确认订单草稿并给用户展示。"""
        if state.get("errors"):
            return {"final_response": "暂时无法生成可预约方案，请补充信息或换个时间。"}
        # OrderAgent 只生成草稿；真正写订单必须等用户确认后走 OrderService。
        candidate = CandidateOption.model_validate(state["selected_option"])
        schedule = ScheduleOutput.model_validate(state["schedule_check"])
        price = PriceOutput.model_validate(state["price_result"])

        async def step():
            draft = await self.order_agent.draft(candidate=candidate, schedule=schedule, price=price, user_id=state["user_id"])
            return draft.model_dump(mode="json")

        draft = await self.trace_logger.traced(
            trace_id=state["trace_id"], session_id=state.get("session_id"), agent_name="OrderAgent", step_name="present_options", input=state["price_result"], fn=step
        )
        order_draft = validate_output(draft, OrderDraft, agent_name="OrderAgent")

        async def verify_step():
            verification = await self.verification_gate.verify_order_draft(candidate=candidate, schedule=schedule, price=price, draft=order_draft)
            return verification.model_dump(mode="json")

        verification = await self.trace_logger.traced(
            trace_id=state["trace_id"],
            session_id=state.get("session_id"),
            agent_name="VerificationGate",
            step_name="verify_order_draft",
            input=draft,
            fn=verify_step,
        )
        if not verification["passed"]:
            await self.rollback_manager.release_time_lock(order_draft)
            return {"order_draft": draft, "errors": state.get("errors", []) + verification["errors"], "final_response": "预约方案校验未通过，请重新提交预约需求。"}
        return {"order_draft": draft, "final_response": "为你找到以下可预约方案，是否确认预约？"}

    async def customer_service(self, state: AgentState) -> AgentState:
        """LangGraph 节点：先查知识库政策，再生成售后建议并创建售后工单。"""
        intent = IntentOutput.model_validate(state["intent"])

        async def step():
            # 1. 查询知识库：根据任务类型获取相关政策
            knowledge_context: str | None = None
            try:
                from app.tools.search_tools import search_knowledge
                # 按任务类型映射到知识库查询
                query_map = {
                    "refund_request": "退款政策 退款标准 退款流程",
                    "complaint": "投诉处理标准 投诉流程 补偿标准",
                    # SQL 关键词检索按空格分词，取消/预约/规则拆开能稳定命中种子知识库。
                    "cancel_order": "取消 预约 规则",
                    "reschedule_order": "改期规则 修改预约时间",
                }
                kb_query = query_map.get(intent.task_type, "售后政策 门店规则")
                result = await search_knowledge(
                    knowledge_repo=self.knowledge_agent.repo,
                    query=kb_query,
                )
                if result.get("hits"):
                    knowledge_context = "\n".join(
                        f"{h['title']}: {h['content']}" for h in result["hits"][:2]
                    )
                # 提取结构化证据链用于 policy_basis
                evidence_for_ticket = result.get("evidence", [])
                # SQL 关键词回退有时只有 hits、没有 evidence；这里转成统一证据形状，保证工单仍有政策依据。
                if not evidence_for_ticket and result.get("hits"):
                    evidence_for_ticket = [
                        {
                            "source_file": h.get("source", h.get("title", "")),
                            "doc_type": h.get("category", ""),
                            "chunk_id": h.get("id", ""),
                            "score": h.get("score", 1.0),
                            "text": h.get("content", ""),
                        }
                        for h in result["hits"][:2]
                    ]
            except Exception:
                evidence_for_ticket = []

            # 2. 生成售后建议（带知识上下文）
            output = await self.customer_service_agent.run(
                message=state["user_message"],
                intent=intent,
                knowledge_context=knowledge_context,
            )
            ticket = await self.after_sales_service.create_ticket(
                trace_id=state["trace_id"],
                session_id=state.get("session_id"),
                user_id=state["user_id"],
                output=output,
                policy_basis=evidence_for_ticket if evidence_for_ticket else None,
            )
            return {
                "recommendation": output.model_dump(mode="json"),
                "ticket": {
                    "id": str(ticket.id),
                    "ticket_type": ticket.ticket_type,
                    "status": ticket.status,
                    "priority": ticket.priority,
                    "summary": ticket.summary,
                    "suggested_action": ticket.suggested_action,
                },
            }

        output = await self.trace_logger.traced(
            trace_id=state["trace_id"],
            session_id=state.get("session_id"),
            agent_name="CustomerServiceAgent",
            step_name="create_after_sales_ticket",
            input={"message": state["user_message"], "intent": state["intent"]},
            fn=step,
        )
        # Contract 校验 + 售后门禁
        cs_output = validate_output(output["recommendation"], CustomerServiceOutput, agent_name="CustomerServiceAgent")
        after_sale_check = await self.verification_gate.verify_after_sale_request(
            intent=intent, output=cs_output,
        )
        if not after_sale_check.passed:
            logger.warning("售后服务请求门禁校验失败: %s", after_sale_check.errors)
        ticket = output["ticket"]
        return {
            "customer_service_result": output["recommendation"],
            "after_sales_ticket": ticket,
            "final_response": f"已创建售后工单 {ticket['id']}，处理建议：{ticket['suggested_action']}",
        }
