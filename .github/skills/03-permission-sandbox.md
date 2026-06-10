# 权限控制与分层沙箱

## 一句话总结
Agent 不能直接写数据库。每个工具调用经过 ToolSpec 元数据→PermissionManager 白名单→AgentToolSandbox 参数校验→超时保护→审计日志五层治理链，并用 TaskIsolationSandbox 隔离并发请求。

## 五层工具治理链

```
Agent.call("create_order", args)
  │
  ├─ 1. ToolSpec 元数据校验
  │     risk_level=high, mutating=True, allowed_agents=["OrderAgent"]
  │     timeout=5s, retryable=False
  │
  ├─ 2. PermissionManager 白名单
  │     IntentAgent → [] (无任何工具权限)
  │     OrderAgent  → [create_order, get_order, ...]
  │     越权 → PermissionError + 审计日志 PERMISSION_DENIED
  │
  ├─ 3. AgentToolSandbox 参数沙箱
  │     校验参数名/类型，阻止注入额外参数
  │
  ├─ 4. 超时保护 + 重试
  │     asyncio.wait_for(timeout)
  │     失败→retry(if retryable)→审计 TOOL ❌
  │
  └─ 5. 审计日志
        TOOL ✅ agent=OrderAgent tool=create_order risk=high latency=45ms
```

## 三层沙箱架构

| 层级 | 组件 | 职责 |
|---|---|---|
| Agent 工具沙箱 | `AgentToolSandbox` | 校验工具参数名在白名单内 |
| 任务隔离沙箱 | `TaskIsolationSandbox` | ContextVar 绑定 trace_id/session_id/user_id，防止跨请求状态污染 |
| 容器沙箱 | Docker | 非 root 用户、只读文件系统、tmpfs 临时目录 |

## ToolSpec 22 个工具分级

| 风险等级 | 工具 | 数量 |
|---|---|---|
| high | create_order, create_risk_record | 2 |
| medium | check_schedule, create_time_lock, release_time_lock, check_user_risk | 4 |
| low | search_services, search_knowledge, get_order, calculate_price... | 16 |

## 面试重点

**Q: Agent 能直接写数据库吗？**
A: 不能。Agent → ToolRegistry → PermissionManager → AgentToolSandbox → [工具函数] → Service → Repository → DB。6 层调用链，Agent 在最外层，最终写入由 OrderService 的 DB 事务层做最后一次冲突复查。

**Q: 22 个工具怎么防止越权？**
A: 每个工具有 ToolSpec 元数据声明 allowed_agents、risk_level、mutating。IntentAgent 白名单为空——即使 LLM 幻觉让它调用 create_order，PermissionManager 也会拦截并记录 PERMISSION_DENIED 日志。

**Q: 如何防止并发请求状态串扰？**
A: TaskIsolationSandbox 用 Python ContextVar 绑定 trace_id/session_id/user_id。每次 run() 创建新的 task context，异步协程间自动隔离。

**关键数字**：22 工具 | 5 层治理 | 3 层沙箱 | 10 Agent 权限白名单
