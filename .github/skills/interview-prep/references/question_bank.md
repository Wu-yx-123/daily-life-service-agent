# 模拟面试题库

## 项目总览

1. 介绍 MassageOps-Agent 的业务背景和技术架构。
2. 为什么说它不是普通 chatbot？
3. Phase 1 的闭环是什么？

## Agent 与 Harness

1. LangGraph 在这里解决什么问题？
2. Orchestrator 做了哪些事？
3. 为什么 Agent 输出必须结构化？
4. ToolRegistry 和 PermissionManager 分别负责什么？
5. 为什么要拆成多个 Agent，而不是一个 Agent 一次性完成预约？
6. 哪些 Agent 适合调用大模型，哪些不应该调用？
7. `VerificationGate` 在 Multi-Agent 流程里解决什么问题？
8. 售后类任务如何从预约主链路分支出去？
9. 如果 `ScheduleAgent` 返回不可用，工作流应该如何结束或推荐替代时间？

## 排班与订单

1. ScheduleAgent 如何判断某个时间可约？
2. Redis 时间锁解决什么问题？
3. 为什么 OrderService 还要做数据库冲突复查？
4. 订单确认为什么只提交 trace_id 和 option_id？

## Trace 与可观测性

1. AgentTrace 表有哪些字段？
2. TraceLogger 如何记录成功和失败？
3. 前端 Trace 时间线展示哪些内容？

## Agent 记忆

1. 当前项目实现了哪些类型的 Agent 记忆？
2. 为什么 `agent_run:{trace_id}` 不能等同于长期会话记忆？
3. KnowledgeAgent 的 RAG 检索如何参与售后和风控？
4. RiskAgent 使用了哪些用户历史指标？
5. 如果要支持多轮补槽，数据库、Repository 和 Orchestrator 分别要怎么改？

## 沙箱

1. AgentToolSandbox 和 PermissionManager 有什么区别？
2. 为什么变更型工具必须运行在任务沙箱里？
3. 任务级隔离如何防止串线？
4. Docker 容器运行沙箱做了哪些限制？

## 前端

1. ChatPage 的状态有哪些？
2. BookingOptionCard 为什么不让用户提交价格？
3. 前端测试 mock 了哪些 API？
