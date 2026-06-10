# 项目亮点

## 技术亮点

- FastAPI + SQLAlchemy 2.x 搭建异步后端。
- PostgreSQL 设计用户、门店、服务、技师、房间、排班、订单、Trace 表。
- Redis 实现临时时间锁、订单确认幂等 Key、Agent 运行态缓存。
- LangGraph 编排多 Agent 状态机。
- Multi-Agent 职责拆分：意图解析、任务规划、服务匹配、排班锁定、价格计算、风控审批、订单草稿生成。
- Harness Orchestrator 管理 trace、工具注册、权限、执行状态。
- Agent 记忆分层：运行态缓存、知识库检索、用户历史风险指标、TraceLog 复盘。
- Agent TraceLog 支持全过程可观测。
- 三层沙箱增强安全边界。
- React + TypeScript 实现聊天预约体验。
- pytest 与 Vitest 覆盖关键流程。

## 业务亮点

- 用户自然语言表达“今晚8点、90分钟肩颈、预算300以内、力度重一点”。
- 系统自动解析意图、匹配服务和技师、检查排班、计算价格、生成订单草稿。
- 用户确认后创建正式订单。

## 推荐 Bullet

- 基于 FastAPI、LangGraph 和 Redis 构建按摩预约多 Agent 平台，实现自然语言预约到订单创建的 Phase 1 MVP 闭环。
- 基于 LangGraph 构建多 Agent 预约工作流，将意图识别、任务规划、服务匹配、排班锁定、计价、风控和订单草稿生成拆分为可验证节点。
- 设计 Harness Orchestrator，将 Agent 输出、工具调用、权限校验和 TraceLog 纳入统一控制，避免 Agent 直接操作数据库。
- 实现 Redis 时间锁和订单确认幂等 Key，并在 OrderService 中进行数据库冲突复查，降低重复预约风险。
- 构建 Agent 工具权限沙箱、任务级隔离沙箱和 Docker 容器运行沙箱，提升 Agent 执行业务动作的安全性。
- 设计 Agent 上下文持久化方案，结合 Redis 运行态缓存、知识库检索、用户历史风险指标和 TraceLog，支撑订单确认、风控判断和执行复盘。
- 使用 React + TypeScript 实现聊天预约页、候选预约卡片和 Agent Trace 时间线，补充前后端自动化测试。

## Multi-Agent 表达

推荐简历表达：

- 设计 Multi-Agent 任务编排：通过 LangGraph 将预约流程拆分为 `IntentAgent -> PlannerAgent -> MatchAgent -> ScheduleAgent -> PriceAgent -> RiskAgent -> ApprovalGate -> OrderAgent`，支持追问、售后和审批等条件分支。
- 设计 LLM 与确定性服务边界：`IntentAgent` 负责自然语言结构化解析，排班、计价、订单创建等高一致性动作由 service 层执行，并通过 `VerificationGate` 做二次校验。
- 建立 Agent 工具调用治理：通过 `ToolRegistry`、`PermissionManager` 和 `AgentToolSandbox` 限制不同 Agent 的工具权限和参数范围，降低越权调用风险。

不要写成：

- 所有 Agent 都由大模型自主决策。
- Agent 可以直接创建订单或修改数据库。
- Multi-Agent 已支持任意复杂任务自动规划。

## Agent 记忆表达

推荐简历表达：

- 设计 Agent 上下文持久化机制：使用 Redis `agent_run:{trace_id}` 保存运行态草稿，结合 MCP RAG/SQL 知识库检索、用户历史风险指标和 Agent TraceLog，支撑订单确认、风险评估和执行复盘。
- 规划多轮会话记忆扩展：基于 `session_id/user_id` 持久化历史消息，在 `IntentAgent` 前注入最近上下文，以支持追问补槽和跨轮预约需求合并。

不要写成：

- 已实现完整长期记忆。
- 已实现向量化用户画像。
- 已支持所有跨轮对话自动合并。
