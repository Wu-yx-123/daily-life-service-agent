# 架构说明

## 请求链路

```text
React ChatPage
-> POST /api/v1/conversations/message
-> HarnessOrchestrator
-> LangGraph
-> IntentAgent
-> PlannerAgent
-> MatchAgent
-> ScheduleAgent
-> PriceAgent
-> OrderAgent
-> ConversationResponse
```

确认订单：

```text
POST /api/v1/orders/confirm
-> 读取 agent_run:{trace_id}
-> 校验 option_id
-> Redis 幂等 Key
-> OrderService
-> OrderRepository
-> orders 表
```

## 分层原则

- API 层只处理请求/响应。
- Orchestrator 管理 Agent 工作流。
- Agent 只输出结构化结果，不直接写数据库。
- ToolRegistry 负责工具调用入口。
- Service 层执行业务规则。
- Repository 层做数据库访问。
- TraceLogger 记录每个 Agent 节点。

## 沙箱

- `AgentToolSandbox`：工具和参数白名单。
- `TaskIsolationSandbox`：trace/session/user 隔离。
- Docker 沙箱：容器运行限制。

## 记忆系统

```text
Redis SessionStore
-> 短期会话记忆，保存最近消息和上一轮 AgentState。

PostgreSQL user_preferences
-> 结构化长期记忆，保存服务、力度、预算、技师、常用时段等偏好。

PostgreSQL pgvector user_memory_chunks
-> 语义长期记忆，保存用户私有自然语言经验摘要。

MCP RAG / SQL fallback
-> 平台共享知识库，保存服务说明、售后政策、风控规则和话术模板。
```

开发规则：

- 用户记忆和平台知识库必须分离。
- pgvector 召回必须按 `user_id` 隔离。
- 语义记忆只能辅助理解，不能替代用户本轮确认。
- 新增上下文字段时要同时接入 `run` 和 `stream_run`。
- 增强能力失败时要降级，不影响预约主链路。
