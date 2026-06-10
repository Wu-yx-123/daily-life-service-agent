# 核心功能

## Phase 1 已实现

- 用户输入自然语言预约需求。
- IntentAgent 解析服务类型、时长、时间、预算、力度偏好。
- MatchAgent 匹配服务和技师。
- ScheduleAgent 检查技师排班、房间可用性，创建时间锁。
- PriceAgent 计算价格并生成价格快照。
- OrderAgent 生成订单草稿。
- 用户确认后创建订单。
- Agent Trace 可查询。
- 前端展示聊天、候选卡、确认按钮和 Trace 时间线。

## 安全与控制

- Agent 工具权限白名单。
- 工具参数白名单。
- 变更型工具必须在任务沙箱中运行。
- `trace_id/session_id/user_id` 任务级隔离。
- Docker 非 root、只读、cap drop。

## 不在 Phase 1 范围

- 真实支付。
- 短信通知。
- 风控审批后台。
- 售后退款完整闭环。
- 运营分析报表。
- ChromaDB / Elasticsearch。
