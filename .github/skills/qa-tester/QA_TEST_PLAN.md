# MassageOps-Agent QA Test Plan

## A. 后端 API

| ID | 场景 | 预期 |
|---|---|---|
| A-01 | `POST /api/v1/conversations/message` 正常预约 | 返回 `booking_options` |
| A-02 | 缺少服务类型/时间 | 返回追问，不创建订单 |
| A-03 | `POST /api/v1/orders/confirm` 正常确认 | 创建 confirmed 订单 |
| A-04 | 重复确认 | 第二次返回 duplicate |
| A-05 | option_id 不匹配 | 返回 400 |
| A-06 | 查询 Trace | 返回 Intent/Planner/Match/Schedule/Price/Order 步骤 |

## B. 业务服务

| ID | 场景 | 预期 |
|---|---|---|
| B-01 | 技师同一时间已有订单 | ScheduleService 返回不可用 |
| B-02 | 房间占用 | 自动尝试其他房间或返回不可用 |
| B-03 | 门店非营业时间 | 返回不可用 |
| B-04 | 订单创建前冲突复查 | 冲突时拒绝写入 |

## C. 沙箱

| ID | 场景 | 预期 |
|---|---|---|
| C-01 | IntentAgent 调 create_order | 拒绝 |
| C-02 | 工具参数包含额外字段 | 拒绝 |
| C-03 | 变更型工具脱离任务上下文 | 拒绝 |
| C-04 | state trace_id 与当前上下文不一致 | 拒绝 |

## D. 前端

| ID | 场景 | 预期 |
|---|---|---|
| D-01 | 发送预约需求 | 显示候选卡 |
| D-02 | 点击确认预约 | 显示预约成功 |
| D-03 | Trace 时间线 | 显示 Agent 步骤 |

## E. Docker

| ID | 场景 | 预期 |
|---|---|---|
| E-01 | 后端容器 | 非 root、只读、cap drop |
| E-02 | 前端容器 | 非 root、只读、cap drop |
| E-03 | Postgres/Redis | no-new-privileges |
