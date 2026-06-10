# MassageOps-Agent 项目知识

## 当前已实现

- FastAPI 后端应用入口：`backend/app/main.py`
- API 路由：
  - `conversations.py`
  - `orders.py`
  - `agent_runs.py`
- Agent：
  - `IntentAgent`
  - `PlannerAgent`
  - `MatchAgent`
  - `ScheduleAgent`
  - `PriceAgent`
  - `OrderAgent`
- Harness：
  - `HarnessOrchestrator`
  - `ToolRegistry`
  - `PermissionManager`
  - `TraceLogger`
  - `AgentToolSandbox`
  - `TaskIsolationSandbox`
- 数据模型：
  - `User`
  - `Store`
  - `Service`
  - `Technician`
  - `Room`
  - `TechnicianSchedule`
  - `Order`
  - `AgentTrace`
- 前端：
  - `ChatPage`
  - `BookingOptionCard`
  - `AgentTimeline`

## Multi-Agent 编排

- 工作流：`IntentAgent -> VerificationGate -> PlannerAgent -> MatchAgent -> ScheduleAgent -> PriceAgent -> RiskAgent -> ApprovalGate -> OrderAgent`。
- 售后分支：`PlannerAgent` 根据任务类型把取消、改期、退款、投诉路由到 `CustomerServiceAgent`。
- LLM 边界：`IntentAgent` 优先使用 LLM structured output，失败回退正则；排班、计价、订单创建保持确定性。
- 状态传递：`AgentState` 保存 `trace_id`、`intent`、`selected_option`、`schedule_check`、`price_result`、`risk_result`、`order_draft` 等跨节点数据。
- 工具治理：Agent 通过 `ToolRegistry` 调用工具，并受 `PermissionManager`、`AgentToolSandbox` 和参数白名单限制。
- 安全校验：`VerificationGate` 在意图、候选、排班、价格和订单草稿阶段做确定性校验，防止 Agent 幻觉进入核心交易链路。

## 关键业务规则

- Agent 不直接写数据库。
- 订单创建必须走 `OrderService`。
- 排班成功会创建 Redis 时间锁。
- 确认订单使用 Redis 幂等 Key。
- 写订单前再次查数据库冲突。
- TraceLog 记录每个 Agent 节点。

## Agent 记忆

- 运行态记忆：`AgentRunStore` 和 Redis `agent_run:{trace_id}` 保存完整 AgentState，订单确认时读取 `order_draft`。
- 知识库记忆：`KnowledgeAgent` / `search_knowledge` 优先 MCP RAG，失败回退 SQL 关键词检索。
- 业务历史记忆：`RiskAgent` 查询用户取消、退款和订单历史，用于风险判断。
- Trace 记忆：`agent_traces` 保存节点输入、输出、状态、耗时和异常，用于复盘。
- Phase 边界：当前还没有完整多轮会话长期记忆；`session_id` 主要用于隔离和追踪。

## 沙箱

- `AgentToolSandbox` 检查工具和参数。
- `TaskIsolationSandbox` 检查 trace/session/user。
- Docker Compose 使用非 root、只读、cap drop、no-new-privileges。
