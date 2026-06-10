# Multi-Agent 协同架构

## 一句话总结
基于 LangGraph + 自研 Harness Orchestrator，将按摩预约全链路拆解为 11 个专业 Agent + 14 个 LangGraph 节点，通过状态机驱动条件路由，实现从自然语言输入到订单创建的全流程自动化。

## 架构总览

```
用户输入 → IntentAgent → VerificationGate → PlannerAgent → MatchAgent
  → ScheduleAgent → PriceAgent → RiskAgent → ApprovalGate → OrderAgent
  → CustomerServiceAgent
```

## 11 个 Agent 角色

| Agent | 职责 | LLM |
|---|---|---|
| IntentAgent | 解析自然语言→结构化意图+槽位 | ✅ qwen-plus |
| PlannerAgent | 任务类型→执行计划路由 | 纯路由 |
| MatchAgent | 服务+技师匹配，规则打分 | 纯规则 |
| ScheduleAgent | 排班校验+Redis时间锁 | 纯规则 |
| PriceAgent | 价格计算+快照 | 纯规则 |
| RiskAgent | 6维业务历史风险评分 | 规则+DB |
| OrderAgent | 订单草稿组装 | 纯规则 |
| ApprovalGate | 高风险→人工审批单 | 规则 |
| CustomerServiceAgent | 售后建议生成 | ✅ LLM+政策 |
| ReviewAgent | 评价情感分析 | ✅ LLM |
| KnowledgeAgent | 知识库检索 | MCP RAG |
| OpsAgent | 运营报表生成 | 规则+统计 |

## 14 个 LangGraph 节点 + 条件路由

```
parse_intent → verify_intent → plan_task
  ├─ book_appointment → match_service → check_schedule
  │   → calculate_price → risk_check → approval_gate → present_options
  ├─ cancel/reschedule/refund/complaint → customer_service
  └─ service_query/store_query → plan_task即时回复
```

## 面试重点

**Q: 为什么用 LangGraph 而不是手写 if-else？**
A: LangGraph 提供 StateGraph 状态机，支持条件分支、错误回退。14 个节点串成业务闭环，verify_intent 失败→END 追问，schedule 不可用→推荐替代时间，风险高→审批 Gate。每个节点在 TraceLogger 中记录输入/输出/耗时/错误。

**Q: 哪些 Agent 适合接 LLM，哪些不适合？**
A: 语义理解类（IntentAgent, CustomerServiceAgent, ReviewAgent）接 LLM 效果显著提升；确定性计算类（MatchAgent评分, ScheduleAgent冲突检测, PriceAgent价格）纯规则更安全——不能因为 LLM 幻觉导致多收钱或双人抢同一时段。

**Q: Agent 之间怎么通信？**
A: 共享 AgentState（TypedDict），14 个节点按序读写同一份状态。Orchestrator 负责注入知识库检索结果到 CustomerServiceAgent、用户历史到 RiskAgent，Agent 本身不互相调用。

**关键数字**：14 节点 | 11 Agent | 22 工具 | 39 测试 | 24 eval | 7 迁移
