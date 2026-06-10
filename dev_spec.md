<!-- 作用：项目开发规格说明书，定义 MassageOps-Agent 的架构、阶段和验收标准。 -->
# dev_spec.md

# 按摩运营智能体平台开发规格说明书

## 1. 项目概述

### 1.1 项目名称

**MassageOps-Agent：基于 Harness Engineering 的按摩运营智能体平台**

### 1.2 项目定位

本项目是一个面向按摩、SPA、理疗、足疗等本地生活服务场景的 **多 Agent 智能预约与运营平台**。

系统不只是一个聊天机器人，而是一个具备业务执行能力的智能运营平台，覆盖以下核心业务链路：

- 用户自然语言预约
- 服务项目推荐
- 技师与房间排班
- 预约冲突检测
- 价格与优惠计算
- 风险审核
- 订单创建
- 售后处理
- 评价分析
- 商家运营报表
- Agent 执行轨迹可视化

本项目基于 **Harness Engineering** 思想进行设计，即通过工程化的外部执行框架约束 Agent 行为，避免 Agent 自由发挥导致业务不可控。

核心设计原则：

```text
Agent 不直接拥有最终业务写权限
Agent 的每一步输出都必须结构化
Agent 的关键动作必须经过校验器
高风险操作必须进入人工审核
所有工具调用都必须记录执行轨迹
所有业务流程都必须被状态机管理
```

### 1.3 项目目标

构建一个可以真实落地的按摩运营智能体平台，支持用户侧预约、商家侧管理、平台侧风控与运营分析。

项目最终应具备：

1. 用户可以通过自然语言完成预约。
2. 系统可以自动理解服务类型、时间、预算、偏好等信息。
3. 系统可以根据门店、技师、房间、服务项目和时间段进行匹配。
4. 系统可以检查排班冲突，避免重复预约。
5. 系统可以计算价格、优惠券、会员价和套餐价。
6. 系统可以通过风控 Agent 审核异常订单。
7. 系统可以处理改期、取消、退款、投诉等售后场景。
8. 系统可以为商家生成运营分析报告。
9. 系统可以展示 Agent 的执行过程，包括规划、工具调用、观察结果、校验和最终输出。
10. 系统具备可测试、可观测、可扩展、可回滚的工程能力。

---

## 2. 核心特点

### 2.1 基于 Harness Engineering 的可控 Agent 架构

本项目不采用“一个大模型直接操作数据库”的方式，而是使用 Harness Orchestrator 作为 Agent 外部执行框架。

Harness 层负责：

- 管理任务状态
- 调度不同 Agent
- 限制 Agent 工具权限
- 校验 Agent 输出
- 决定是否进入人工审核
- 管理重试和失败回滚
- 记录全链路 TraceLog
- 输出可视化执行轨迹

标准执行流程：

```text
User Request
    ↓
Intent Parse
    ↓
Plan Workflow
    ↓
Tool Execution
    ↓
Observation
    ↓
Verification Gate
    ↓
Risk Check
    ↓
Human Approval, if needed
    ↓
Commit Business Action
    ↓
Trace Log
    ↓
Final Response
```

### 2.2 多 Agent 分工协作

系统拆分为多个专业 Agent，每个 Agent 只负责明确边界内的任务。

| Agent | 职责 |
|---|---|
| PlannerAgent | 分解用户任务，决定执行流程 |
| IntentAgent | 解析用户自然语言需求 |
| MatchAgent | 匹配服务、门店、技师 |
| ScheduleAgent | 检查技师、房间、时间段冲突 |
| PriceAgent | 计算价格、会员折扣、优惠券 |
| RiskAgent | 审核异常订单和违规内容 |
| OrderAgent | 生成待确认订单，提交创建请求 |
| CustomerServiceAgent | 处理取消、改期、退款、投诉 |
| ReviewAgent | 分析用户评价和差评原因 |
| OpsAgent | 生成经营分析报告 |
| KnowledgeAgent | 查询服务说明、门店规则、售后政策 |

### 2.3 Agent Contract 约束输入输出

每个 Agent 必须通过固定的 JSON Schema 输入输出。

禁止 Agent 返回不可解析的自由文本作为业务执行依据。

示例：

```json
{
  "agent": "IntentAgent",
  "input": {
    "message": "今晚8点想约一个90分钟肩颈按摩，预算300以内，力度重一点"
  },
  "output": {
    "service_type": "肩颈按摩",
    "duration_minutes": 90,
    "preferred_time": "2026-05-29T20:00:00+09:00",
    "budget_max": 300,
    "strength_preference": "heavy",
    "missing_slots": []
  }
}
```

### 2.4 Verification Gate 校验机制

Agent 的输出不能直接进入下一步业务执行，必须经过 Verification Gate。

例如：

- 时间是否合法
- 服务项目是否存在
- 技师是否真实存在
- 技师是否属于该门店
- 房间是否空闲
- 价格是否被篡改
- 用户是否已确认
- 风控是否通过

### 2.5 Tool Permission 工具权限控制

不同 Agent 只能调用自己被授权的工具。

| Agent | 读权限 | 写权限 |
|---|---|---|
| IntentAgent | 无 | 无 |
| MatchAgent | 服务、门店、技师、评价 | 无 |
| ScheduleAgent | 排班、房间、订单 | 可创建临时时间锁 |
| PriceAgent | 服务价格、优惠券、会员信息 | 无 |
| RiskAgent | 用户历史、订单历史、黑名单 | 可创建风控记录 |
| OrderAgent | 待确认订单、时间锁、价格快照 | 可创建订单 |
| CustomerServiceAgent | 订单、售后政策、评价 | 可创建售后工单 |
| OpsAgent | 订单、评价、营收统计 | 无 |

### 2.6 Agent Trace 可观测性

每一次 Agent 执行都必须记录：

- trace_id
- session_id
- order_id
- agent_name
- step_name
- input
- output
- tool_name
- tool_args
- tool_result
- status
- latency_ms
- error_message
- created_at

前端需要展示完整执行轨迹：

```text
1. IntentAgent：解析用户需求成功
2. PlannerAgent：决定进入预约流程
3. MatchAgent：召回 5 个候选服务
4. ScheduleAgent：检查技师和房间可用性
5. PriceAgent：计算最终价格
6. RiskAgent：风控通过
7. OrderAgent：生成待确认订单
8. 用户确认
9. OrderAgent：创建订单成功
```

### 2.7 Human-in-the-loop 人工审核

以下场景必须转人工：

- 高金额退款
- 用户投诉
- 风控中高风险订单
- 用户要求特殊服务
- 商家临时改价
- 技师被投诉次数较多
- 订单数据冲突
- Agent 多次执行失败

人工审核流程：

```text
Agent 提交建议
    ↓
系统生成审核单
    ↓
管理员查看上下文和执行轨迹
    ↓
管理员批准 / 驳回 / 修改
    ↓
系统继续执行或终止流程
```

---

## 3. 技术选型

### 3.1 总体技术栈

```text
Frontend:
- React
- TypeScript
- Tailwind CSS
- shadcn/ui 或 Ant Design
- React Query
- Zustand
- React Flow, 用于 Agent 工作流可视化

Backend:
- FastAPI
- Python 3.11+
- SQLAlchemy 2.x
- Alembic
- Pydantic v2

Database:
- PostgreSQL

Cache / Queue:
- Redis

Agent Orchestration:
- LangGraph
- 自研 Harness Orchestrator

Vector / Search:
- ChromaDB, 用于快速本地向量检索
- Elasticsearch, 用于关键词检索、日志检索、BM25

LLM Provider:
- OpenAI-compatible API
- DeepSeek / Qwen / Claude-compatible endpoint
- 后端通过统一 ModelProvider 接口适配

Observability:
- 结构化日志
- Agent TraceLog
- 可选 OpenTelemetry

Testing:
- pytest
- pytest-asyncio
- httpx
- factory_boy
- Playwright
```

### 3.2 前端技术说明

前端需要包含三个主要入口：

#### 用户端

功能：

- 自然语言预约
- 服务推荐卡片
- 候选时间选择
- 价格确认
- 订单确认
- 订单取消 / 改期
- 售后咨询

#### 商家端

功能：

- 门店管理
- 服务项目管理
- 技师管理
- 房间管理
- 排班管理
- 订单管理
- 评价管理

#### 平台运营端

功能：

- 风控审核
- 人工审批
- Agent 执行轨迹
- 运营报表
- 异常订单监控
- 系统配置

### 3.3 后端技术说明

后端使用 FastAPI，按模块划分：

```text
backend/
  app/
    main.py
    core/
      config.py
      security.py
      logging.py
      redis.py
      database.py
    api/
      v1/
        routes/
          auth.py
          users.py
          stores.py
          services.py
          technicians.py
          rooms.py
          schedules.py
          orders.py
          conversations.py
          agent_runs.py
          approvals.py
          ops.py
    models/
      user.py
      store.py
      service.py
      technician.py
      room.py
      schedule.py
      order.py
      coupon.py
      review.py
      agent_trace.py
      approval.py
    schemas/
      user.py
      store.py
      service.py
      order.py
      agent.py
    services/
      order_service.py
      schedule_service.py
      price_service.py
      risk_service.py
      search_service.py
    agents/
      graph.py
      state.py
      contracts.py
      planner_agent.py
      intent_agent.py
      match_agent.py
      schedule_agent.py
      price_agent.py
      risk_agent.py
      order_agent.py
      customer_service_agent.py
      ops_agent.py
    harness/
      orchestrator.py
      tool_registry.py
      permission.py
      verification.py
      trace.py
      rollback.py
      approval_gate.py
    tools/
      service_tools.py
      schedule_tools.py
      order_tools.py
      price_tools.py
      risk_tools.py
      search_tools.py
      notification_tools.py
    repositories/
      user_repo.py
      store_repo.py
      order_repo.py
      schedule_repo.py
    tests/
```

### 3.4 数据库选型

PostgreSQL 用于存储核心业务数据：

- 用户
- 门店
- 服务项目
- 技师
- 房间
- 排班
- 订单
- 优惠券
- 评价
- 售后工单
- Agent 执行记录
- 人工审批记录

Redis 用于：

- 会话缓存
- 临时时间锁
- 幂等 Key
- Agent 执行状态缓存
- 任务队列
- 限流

ChromaDB 用于：

- 服务说明文档向量检索
- 售后政策检索
- 商家规则检索
- 常见问题检索

Elasticsearch 用于：

- 服务关键词搜索
- 订单日志搜索
- Agent Trace 检索
- BM25 检索
- 运营分析基础查询

### 3.5 LangGraph 选型说明

LangGraph 用于构建有状态 Agent 工作流。

适合本项目的原因：

1. 支持 StateGraph，可以维护预约流程状态。
2. 支持条件分支，适合风控、校验、人工审批。
3. 支持多节点 Agent 编排。
4. 支持重试、失败分支和循环。
5. 适合构建 Plan → Tool Use → Verify → Final 的流程。

本项目不应直接把业务逻辑散落在 prompt 中，而应将 LangGraph 作为状态机和执行图，业务规则放入 service 和 verification 层。

---

## 4. 系统架构与模块设计

## 4.1 总体架构

```text
用户 / 商家 / 管理员
        ↓
React Frontend
        ↓
FastAPI Backend
        ↓
Harness Orchestrator
        ↓
LangGraph Agent Workflow
        ↓
Tool Registry
        ↓
Business Services
        ↓
PostgreSQL / Redis / ChromaDB / Elasticsearch
```

### 4.2 分层架构

```text
Presentation Layer
- React 页面
- Chat UI
- 订单面板
- 审批台
- Agent Trace 可视化

API Layer
- FastAPI REST API
- SSE / WebSocket Agent Streaming

Application Layer
- OrderService
- ScheduleService
- PriceService
- RiskService
- SearchService

Harness Layer
- Orchestrator
- Tool Permission
- Verification Gate
- Approval Gate
- Trace Logger
- Rollback Manager

Agent Layer
- PlannerAgent
- IntentAgent
- MatchAgent
- ScheduleAgent
- PriceAgent
- RiskAgent
- OrderAgent
- CustomerServiceAgent
- OpsAgent

Tool Layer
- SQL Tools
- Schedule Tools
- Order Tools
- Price Tools
- Risk Tools
- Search Tools
- Notification Tools

Data Layer
- PostgreSQL
- Redis
- ChromaDB
- Elasticsearch
```

---

## 4.3 核心业务流程一：自然语言预约

### 4.3.1 用户输入示例

```text
今晚8点想约一个90分钟肩颈按摩，预算300以内，最好安排手法重一点的技师。
```

### 4.3.2 执行流程

```text
User Message
  ↓
IntentAgent 解析意图
  ↓
VerificationGate 校验槽位
  ↓
PlannerAgent 判断任务类型为 appointment_booking
  ↓
MatchAgent 匹配服务项目和技师
  ↓
ScheduleAgent 检查时间可用性
  ↓
PriceAgent 计算最终价格
  ↓
RiskAgent 风控审核
  ↓
生成候选预约方案
  ↓
用户确认
  ↓
OrderAgent 创建订单
  ↓
返回订单详情
```

### 4.3.3 LangGraph 节点设计

```text
parse_intent
  ↓
verify_intent
  ↓
plan_task
  ↓
match_service
  ↓
check_schedule
  ↓
calculate_price
  ↓
risk_check
  ↓
present_options
  ↓
wait_user_confirm
  ↓
create_order
  ↓
final_response
```

条件分支：

```text
verify_intent failed → ask_followup
no_available_schedule → recommend_alternative_time
risk_high → human_approval
user_rejected → rematch_service
order_create_failed → rollback_time_lock
```

---

## 4.4 核心业务流程二：改期

用户输入：

```text
我想把今晚8点的预约改到明天下午3点。
```

流程：

```text
IntentAgent 识别为 reschedule_order
  ↓
OrderTool 查询用户当前订单
  ↓
ScheduleAgent 检查新时间
  ↓
RiskAgent 判断是否允许改期
  ↓
VerificationGate 校验旧订单和新时间
  ↓
生成改期方案
  ↓
用户确认
  ↓
释放旧时间锁
  ↓
锁定新时间
  ↓
更新订单
```

---

## 4.5 核心业务流程三：售后退款

用户输入：

```text
技师迟到了20分钟，我想退款。
```

流程：

```text
IntentAgent 识别为 refund_request
  ↓
OrderTool 查询订单
  ↓
CustomerServiceAgent 分析诉求
  ↓
KnowledgeAgent 查询退款政策
  ↓
RiskAgent 判断风险等级
  ↓
生成处理建议
  ↓
如果金额较小，自动创建售后工单
  ↓
如果金额较大，进入人工审核
```

退款不能由 Agent 直接执行，只能生成退款申请或售后工单。

---

## 4.6 核心业务流程四：运营分析

管理员输入：

```text
分析一下本周哪个服务项目收入最高，哪些时间段需要增加技师。
```

流程：

```text
OpsAgent 解析分析任务
  ↓
SQLTool 查询订单、服务、技师、评价数据
  ↓
统计收入、订单量、峰值时段、复购率
  ↓
生成 Markdown 运营分析报告
  ↓
给出排班和营销建议
```

---

## 5. 数据库设计

### 5.1 users 用户表

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY,
    phone VARCHAR(32) UNIQUE,
    nickname VARCHAR(64),
    member_level VARCHAR(32),
    default_location TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### 5.2 stores 门店表

```sql
CREATE TABLE stores (
    id UUID PRIMARY KEY,
    name VARCHAR(128) NOT NULL,
    address TEXT NOT NULL,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    opening_time TIME NOT NULL,
    closing_time TIME NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### 5.3 services 服务项目表

```sql
CREATE TABLE services (
    id UUID PRIMARY KEY,
    store_id UUID REFERENCES stores(id),
    name VARCHAR(128) NOT NULL,
    category VARCHAR(64),
    duration_minutes INT NOT NULL,
    base_price NUMERIC(10,2) NOT NULL,
    description TEXT,
    tags JSONB,
    status VARCHAR(32) DEFAULT 'active',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### 5.4 technicians 技师表

```sql
CREATE TABLE technicians (
    id UUID PRIMARY KEY,
    store_id UUID REFERENCES stores(id),
    name VARCHAR(64) NOT NULL,
    skill_tags JSONB,
    rating NUMERIC(3,2),
    status VARCHAR(32) DEFAULT 'active',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### 5.5 rooms 房间表

```sql
CREATE TABLE rooms (
    id UUID PRIMARY KEY,
    store_id UUID REFERENCES stores(id),
    name VARCHAR(64) NOT NULL,
    room_type VARCHAR(64),
    status VARCHAR(32) DEFAULT 'active'
);
```

### 5.6 technician_schedules 技师排班表

```sql
CREATE TABLE technician_schedules (
    id UUID PRIMARY KEY,
    technician_id UUID REFERENCES technicians(id),
    store_id UUID REFERENCES stores(id),
    work_date DATE NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    status VARCHAR(32) DEFAULT 'available'
);
```

### 5.7 orders 订单表

```sql
CREATE TABLE orders (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    store_id UUID REFERENCES stores(id),
    service_id UUID REFERENCES services(id),
    technician_id UUID REFERENCES technicians(id),
    room_id UUID REFERENCES rooms(id),
    appointment_start TIMESTAMP NOT NULL,
    appointment_end TIMESTAMP NOT NULL,
    original_price NUMERIC(10,2) NOT NULL,
    final_price NUMERIC(10,2) NOT NULL,
    status VARCHAR(32) NOT NULL,
    source VARCHAR(32) DEFAULT 'agent',
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### 5.8 coupons 优惠券表

```sql
CREATE TABLE coupons (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    title VARCHAR(128),
    discount_type VARCHAR(32),
    discount_value NUMERIC(10,2),
    min_order_amount NUMERIC(10,2),
    valid_from TIMESTAMP,
    valid_to TIMESTAMP,
    status VARCHAR(32) DEFAULT 'unused'
);
```

### 5.9 reviews 评价表

```sql
CREATE TABLE reviews (
    id UUID PRIMARY KEY,
    order_id UUID REFERENCES orders(id),
    user_id UUID REFERENCES users(id),
    rating INT NOT NULL,
    content TEXT,
    sentiment VARCHAR(32),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### 5.10 after_sales 售后工单表

```sql
CREATE TABLE after_sales (
    id UUID PRIMARY KEY,
    order_id UUID REFERENCES orders(id),
    user_id UUID REFERENCES users(id),
    issue_type VARCHAR(64),
    description TEXT,
    suggested_solution TEXT,
    status VARCHAR(32),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### 5.11 approvals 人工审批表

```sql
CREATE TABLE approvals (
    id UUID PRIMARY KEY,
    trace_id VARCHAR(128),
    business_type VARCHAR(64),
    business_id UUID,
    request_payload JSONB,
    agent_suggestion JSONB,
    status VARCHAR(32) DEFAULT 'pending',
    reviewer_id UUID,
    review_comment TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### 5.12 agent_traces Agent执行轨迹表

```sql
CREATE TABLE agent_traces (
    id UUID PRIMARY KEY,
    trace_id VARCHAR(128) NOT NULL,
    session_id VARCHAR(128),
    order_id UUID,
    agent_name VARCHAR(128),
    step_name VARCHAR(128),
    input JSONB,
    output JSONB,
    tool_name VARCHAR(128),
    tool_args JSONB,
    tool_result JSONB,
    status VARCHAR(32),
    latency_ms INT,
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

---

## 6. Agent 设计规格

## 6.1 Agent 状态对象

所有 LangGraph 节点共享 AgentState。

```python
from typing import TypedDict, Optional, Any, List, Dict

class AgentState(TypedDict, total=False):
    trace_id: str
    session_id: str
    user_id: str
    user_message: str

    task_type: str
    intent: Dict[str, Any]
    plan: List[Dict[str, Any]]

    candidates: List[Dict[str, Any]]
    selected_option: Optional[Dict[str, Any]]

    schedule_check: Dict[str, Any]
    price_result: Dict[str, Any]
    risk_result: Dict[str, Any]

    approval_required: bool
    approval_id: Optional[str]

    order_draft: Dict[str, Any]
    order_id: Optional[str]

    final_response: str
    errors: List[Dict[str, Any]]
```

## 6.2 IntentAgent

职责：

- 识别任务类型
- 抽取预约槽位
- 判断缺失信息
- 输出结构化意图

支持任务类型：

```text
book_appointment
reschedule_order
cancel_order
refund_request
complaint
service_query
store_query
ops_analysis
unknown
```

输出示例：

```json
{
  "task_type": "book_appointment",
  "slots": {
    "service_type": "肩颈按摩",
    "duration_minutes": 90,
    "preferred_time": "2026-05-29T20:00:00+09:00",
    "budget_max": 300,
    "strength_preference": "heavy",
    "store_preference": null,
    "technician_preference": null
  },
  "missing_slots": [],
  "confidence": 0.92
}
```

## 6.3 PlannerAgent

职责：

- 根据 task_type 选择执行图
- 生成步骤计划
- 决定是否需要调用其他 Agent

预约任务计划：

```json
[
  {"step": "match_service", "agent": "MatchAgent"},
  {"step": "check_schedule", "agent": "ScheduleAgent"},
  {"step": "calculate_price", "agent": "PriceAgent"},
  {"step": "risk_check", "agent": "RiskAgent"},
  {"step": "present_options", "agent": "OrderAgent"}
]
```

## 6.4 MatchAgent

职责：

- 根据意图匹配服务项目
- 匹配技师
- 匹配门店
- 输出候选方案

排序维度：

- 服务类型匹配度
- 时间可用性
- 预算匹配度
- 技师技能标签
- 技师评分
- 用户历史偏好
- 门店距离
- 评价质量

输出示例：

```json
{
  "candidates": [
    {
      "store_id": "store_001",
      "service_id": "service_001",
      "technician_id": "tech_001",
      "service_name": "肩颈舒缓90分钟",
      "technician_name": "小李",
      "base_price": 298,
      "duration_minutes": 90,
      "match_score": 0.91,
      "reason": "符合肩颈按摩、90分钟、预算300以内，技师擅长深层放松"
    }
  ]
}
```

## 6.5 ScheduleAgent

职责：

- 检查技师是否空闲
- 检查房间是否空闲
- 检查营业时间
- 检查服务时长
- 创建临时时间锁
- 推荐替代时间

规则：

```text
预约开始时间必须晚于当前时间 + 30 分钟
预约结束时间不得超过门店营业结束时间
同一技师同一时间不能有两个订单
同一房间同一时间不能有两个订单
服务结束后默认预留 10 分钟清洁时间
临时时间锁默认 10 分钟过期
```

输出示例：

```json
{
  "available": true,
  "room_id": "room_001",
  "lock_id": "lock_abc123",
  "appointment_start": "2026-05-29T20:00:00+09:00",
  "appointment_end": "2026-05-29T21:30:00+09:00",
  "cleanup_end": "2026-05-29T21:40:00+09:00"
}
```

## 6.6 PriceAgent

职责：

- 计算原价
- 计算会员价
- 检查优惠券
- 计算满减
- 生成价格快照

输出示例：

```json
{
  "original_price": 328,
  "member_discount": 20,
  "coupon_discount": 30,
  "promotion_discount": 0,
  "final_price": 278,
  "price_snapshot": {
    "service_id": "service_001",
    "coupon_id": "coupon_001",
    "calculated_at": "2026-05-29T19:30:00+09:00"
  }
}
```

## 6.7 RiskAgent

职责：

- 检查异常订单
- 检查高风险关键词
- 检查频繁取消
- 检查异常退款
- 判断是否需要人工审核

风险规则：

```text
用户 7 天内取消次数 >= 3 → medium
用户 30 天内退款次数 >= 3 → high
订单金额异常低于服务原价 50% → high
包含违规关键词 → high
技师近期投诉率过高 → medium
```

输出示例：

```json
{
  "risk_level": "low",
  "risk_score": 0.12,
  "risk_reasons": [],
  "need_human_approval": false
}
```

## 6.8 OrderAgent

职责：

- 生成订单草稿
- 等待用户确认
- 创建订单
- 释放或确认时间锁
- 返回订单详情

OrderAgent 不允许绕过：

- ScheduleAgent 的时间锁
- PriceAgent 的价格快照
- RiskAgent 的风控结果
- 用户确认

## 6.9 CustomerServiceAgent

职责：

- 处理改期
- 处理取消
- 处理退款申请
- 处理投诉
- 生成补偿建议
- 创建售后工单

限制：

```text
不能直接退款
不能直接删除订单
不能绕过人工审核
不能修改历史评价
```

## 6.10 OpsAgent

职责：

- 生成经营报表
- 分析订单趋势
- 分析服务收入
- 分析技师表现
- 分析高峰时段
- 分析差评原因
- 给出排班和营销建议

输出格式：

```markdown
# 本周运营分析报告

## 1. 核心数据
- 总订单数：
- 总营收：
- 客单价：
- 复购率：

## 2. 热门服务
...

## 3. 高峰时段
...

## 4. 技师表现
...

## 5. 经营建议
...
```

---

## 7. Harness Engineering 设计

## 7.1 Harness Orchestrator

Orchestrator 是系统核心控制器。

职责：

1. 接收用户消息。
2. 创建 trace_id。
3. 初始化 AgentState。
4. 调用 LangGraph。
5. 在每个节点前检查权限。
6. 在每个节点后记录 Trace。
7. 调用 Verification Gate。
8. 判断是否需要人工审核。
9. 处理失败和重试。
10. 返回最终结果。

伪代码：

```python
class HarnessOrchestrator:
    async def run(self, user_id: str, message: str) -> AgentState:
        trace_id = create_trace_id()

        state = AgentState(
            trace_id=trace_id,
            user_id=user_id,
            user_message=message,
            errors=[]
        )

        result = await self.graph.ainvoke(state)

        await self.trace_logger.log_final(result)

        return result
```

## 7.2 Tool Registry

所有工具必须注册到 Tool Registry。

```python
class ToolRegistry:
    def register(self, name: str, tool: callable, allowed_agents: list[str]):
        ...

    async def call(self, agent_name: str, tool_name: str, args: dict):
        self.permission.check(agent_name, tool_name)
        result = await self.tools[tool_name](**args)
        return result
```

## 7.3 Permission Manager

检查 Agent 是否有权调用某个工具。

```python
AGENT_TOOL_PERMISSIONS = {
    "IntentAgent": [],
    "MatchAgent": ["search_services", "search_technicians", "search_reviews"],
    "ScheduleAgent": ["check_schedule", "create_time_lock", "release_time_lock"],
    "PriceAgent": ["calculate_price", "list_available_coupons"],
    "RiskAgent": ["check_user_risk", "create_risk_record"],
    "OrderAgent": ["create_order", "confirm_time_lock"],
    "CustomerServiceAgent": ["get_order", "create_after_sale"],
    "OpsAgent": ["query_order_stats", "query_review_stats"]
}
```

## 7.4 Verification Gate

所有关键业务数据必须经过校验。

```python
class VerificationGate:
    async def verify_intent(self, intent: dict) -> VerificationResult:
        ...

    async def verify_schedule(self, schedule_result: dict) -> VerificationResult:
        ...

    async def verify_price(self, price_result: dict) -> VerificationResult:
        ...

    async def verify_order_draft(self, order_draft: dict) -> VerificationResult:
        ...
```

VerificationResult：

```python
class VerificationResult(BaseModel):
    passed: bool
    reason: str | None = None
    errors: list[dict] = []
```

## 7.5 Approval Gate

判断是否进入人工审核。

```python
class ApprovalGate:
    async def check(self, state: AgentState) -> bool:
        if state["risk_result"]["need_human_approval"]:
            return True
        if state.get("refund_amount", 0) >= 100:
            return True
        return False
```

## 7.6 Rollback Manager

用于失败回滚。

典型场景：

```text
创建订单失败 → 释放时间锁
支付失败 → 释放时间锁
人工审核驳回 → 释放时间锁
用户取消确认 → 释放时间锁
```

---

## 8. API 设计

## 8.1 会话接口

### POST /api/v1/conversations/message

用户发送自然语言消息。

请求：

```json
{
  "session_id": "session_001",
  "user_id": "user_001",
  "message": "今晚8点想约一个90分钟肩颈按摩，预算300以内"
}
```

响应：

```json
{
  "trace_id": "trace_001",
  "session_id": "session_001",
  "response_type": "booking_options",
  "message": "为你找到以下可预约方案",
  "options": [
    {
      "option_id": "option_001",
      "service_name": "肩颈舒缓90分钟",
      "technician_name": "小李",
      "appointment_start": "2026-05-29T20:00:00+09:00",
      "final_price": 278,
      "reason": "符合预算，技师擅长深层肩颈放松"
    }
  ]
}
```

## 8.2 用户确认预约

### POST /api/v1/orders/confirm

请求：

```json
{
  "trace_id": "trace_001",
  "option_id": "option_001",
  "user_confirmed": true
}
```

响应：

```json
{
  "order_id": "order_001",
  "status": "confirmed",
  "message": "预约成功"
}
```

## 8.3 获取 Agent 执行轨迹

### GET /api/v1/agent-runs/{trace_id}

响应：

```json
{
  "trace_id": "trace_001",
  "steps": [
    {
      "agent_name": "IntentAgent",
      "step_name": "parse_intent",
      "status": "success",
      "latency_ms": 300
    },
    {
      "agent_name": "MatchAgent",
      "step_name": "match_service",
      "status": "success",
      "latency_ms": 650
    }
  ]
}
```

## 8.4 人工审批列表

### GET /api/v1/approvals

响应：

```json
{
  "items": [
    {
      "approval_id": "approval_001",
      "business_type": "refund",
      "status": "pending",
      "agent_suggestion": {
        "solution": "建议补偿30元优惠券"
      }
    }
  ]
}
```

## 8.5 审批处理

### POST /api/v1/approvals/{approval_id}/review

请求：

```json
{
  "action": "approve",
  "comment": "同意补偿"
}
```

---

## 9. 前端页面设计

## 9.1 用户预约页面

路径：

```text
/app/chat
```

组件：

```text
ChatWindow
MessageBubble
BookingOptionCard
OrderConfirmPanel
AgentThinkingIndicator
```

功能：

- 用户输入自然语言
- 展示 Agent 思考状态
- 展示预约候选卡片
- 用户点击确认预约
- 支持查看订单详情

## 9.2 商家管理后台

路径：

```text
/admin/store
```

页面：

```text
StoreListPage
ServiceManagePage
TechnicianManagePage
RoomManagePage
ScheduleCalendarPage
OrderManagePage
ReviewManagePage
```

## 9.3 Agent Trace 页面

路径：

```text
/admin/agent-runs/:trace_id
```

组件：

```text
AgentTimeline
AgentStepCard
ToolCallPanel
StateDiffViewer
ErrorPanel
```

展示字段：

- Agent 名称
- 步骤名称
- 状态
- 输入
- 输出
- 工具调用
- 耗时
- 错误信息

## 9.4 人工审批台

路径：

```text
/admin/approvals
```

功能：

- 查看待审批事项
- 查看 Agent 建议
- 查看订单上下文
- 查看执行轨迹
- 批准
- 驳回
- 修改方案

## 9.5 运营分析页面

路径：

```text
/admin/ops
```

功能：

- 输入分析问题
- 展示 Markdown 报告
- 展示图表
- 展示高峰时段
- 展示技师表现
- 展示服务收入排行

---

## 10. 搜索与知识库设计

## 10.1 ChromaDB 文档类型

存储以下知识：

```text
服务项目说明
按摩注意事项
售后退款政策
会员规则
优惠券规则
门店服务规范
常见问题 FAQ
投诉处理标准
```

元数据设计：

```json
{
  "doc_type": "refund_policy",
  "store_id": "store_001",
  "title": "退款规则",
  "version": "2026-05",
  "updated_at": "2026-05-29"
}
```

## 10.2 Elasticsearch 索引

建议索引：

```text
services_index
orders_index
reviews_index
agent_traces_index
```

services_index 字段：

```json
{
  "service_id": "string",
  "store_id": "string",
  "name": "text",
  "category": "keyword",
  "description": "text",
  "tags": "keyword",
  "price": "float",
  "duration_minutes": "integer"
}
```

## 10.3 Hybrid Search

服务匹配可以采用：

```text
BM25 keyword search
    +
Embedding vector search
    +
业务规则打分
    +
RRF 融合排序
```

排序公式示例：

```text
final_score =
0.35 * semantic_score
+ 0.25 * keyword_score
+ 0.20 * technician_rating
+ 0.10 * budget_score
+ 0.10 * user_preference_score
```

---

## 11. Redis 设计

## 11.1 临时时间锁

Key：

```text
time_lock:{store_id}:{technician_id}:{start_time}
```

Value：

```json
{
  "lock_id": "lock_001",
  "user_id": "user_001",
  "trace_id": "trace_001",
  "expires_in": 600
}
```

TTL：

```text
10 分钟
```

## 11.2 幂等 Key

Key：

```text
idempotency:order_confirm:{trace_id}:{option_id}
```

用途：

- 防止用户重复点击确认
- 防止接口重试导致重复创建订单

## 11.3 Agent 执行状态

Key：

```text
agent_run:{trace_id}
```

Value：

```json
{
  "status": "running",
  "current_step": "check_schedule",
  "updated_at": "2026-05-29T20:00:00+09:00"
}
```

---

## 12. 测试方案

## 12.1 测试目标

本项目测试不仅验证 API 是否可用，还要验证 Agent 在业务场景中的稳定性。

测试目标：

1. 核心业务流程可正常完成。
2. Agent 输出符合 JSON Schema。
3. 工具权限控制有效。
4. Verification Gate 能拦截非法数据。
5. 风控规则能正确触发。
6. 人工审批流程能正常衔接。
7. 时间锁和订单创建具备幂等性。
8. 多用户并发预约不会造成排班冲突。
9. 售后流程不会绕过审批。
10. Agent Trace 能完整记录执行链路。

---

## 12.2 单元测试

测试对象：

```text
Intent parser
ScheduleService
PriceService
RiskService
VerificationGate
PermissionManager
ToolRegistry
RollbackManager
```

示例测试：

```python
def test_schedule_conflict_should_fail():
    # given existing order at 20:00-21:30
    # when user tries to book same technician at 20:30
    # then schedule check should return unavailable
    pass
```

```python
def test_risk_should_be_medium_when_user_cancelled_three_times():
    # user cancelled 3 times in 7 days
    # risk level should be medium
    pass
```

```python
def test_agent_cannot_call_unauthorized_tool():
    # IntentAgent should not call create_order
    pass
```

---

## 12.3 API 集成测试

使用 pytest + httpx。

测试接口：

```text
POST /api/v1/conversations/message
POST /api/v1/orders/confirm
GET /api/v1/agent-runs/{trace_id}
GET /api/v1/approvals
POST /api/v1/approvals/{approval_id}/review
```

核心测试场景：

### 场景 1：正常预约

```text
用户输入预约需求
系统返回候选方案
用户确认
订单创建成功
TraceLog 完整
```

### 场景 2：预约时间冲突

```text
同一技师同一时间已有订单
系统不允许创建订单
系统推荐替代时间
```

### 场景 3：缺失槽位

```text
用户只说“我想按摩”
系统追问服务时间或服务类型
不得直接创建订单
```

### 场景 4：高风险订单

```text
用户 7 天内多次取消
RiskAgent 返回 medium
系统进入人工审核
```

### 场景 5：退款申请

```text
用户申请退款
系统创建售后工单
高金额退款进入人工审核
不得直接退款
```

---

## 12.4 Agent Contract 测试

每个 Agent 的输出必须通过 Pydantic 校验。

示例：

```python
class IntentOutput(BaseModel):
    task_type: Literal[
        "book_appointment",
        "reschedule_order",
        "cancel_order",
        "refund_request",
        "complaint",
        "service_query",
        "store_query",
        "ops_analysis",
        "unknown"
    ]
    slots: dict
    missing_slots: list[str]
    confidence: float
```

测试：

```python
def test_intent_agent_output_schema():
    output = intent_agent.run("今晚8点想约肩颈按摩")
    IntentOutput.model_validate(output)
```

---

## 12.5 并发测试

目标：

验证多个用户同时抢同一技师、同一房间、同一时间段时，系统不会重复预约。

测试方式：

```text
同时发送 20 个预约确认请求
期望只有 1 个订单创建成功
其他请求返回时间段已被占用
```

关键点：

- PostgreSQL 事务
- Redis 分布式锁
- 幂等 Key
- 唯一约束
- 乐观锁或悲观锁

---

## 12.6 前端测试

使用 Playwright。

测试页面：

```text
用户预约页面
订单确认页面
Agent Trace 页面
人工审批页面
运营分析页面
```

测试用例：

```text
用户输入预约需求后，页面显示候选卡片
点击确认后，页面显示预约成功
Trace 页面能展示完整节点
审批页面能批准或驳回审核单
```

---

## 12.7 评测集 Golden Test Set

建立标准测试集：

```json
[
  {
    "input": "今晚8点想约一个90分钟肩颈按摩，预算300以内",
    "expected_task_type": "book_appointment",
    "expected_slots": ["service_type", "duration_minutes", "preferred_time", "budget_max"]
  },
  {
    "input": "我想取消今晚的预约",
    "expected_task_type": "cancel_order"
  },
  {
    "input": "技师迟到了20分钟，我想退款",
    "expected_task_type": "refund_request"
  }
]
```

评测指标：

```text
Intent Accuracy
Slot Extraction Accuracy
Tool Call Accuracy
Workflow Completion Rate
Human Approval Trigger Accuracy
Order Creation Success Rate
Schedule Conflict Detection Rate
Average Latency
```

---

## 13. 开发里程碑

## 13.1 Phase 1：MVP 预约闭环

目标：

完成自然语言预约到订单创建的最小闭环。

功能：

```text
用户聊天页面
IntentAgent
MatchAgent
ScheduleAgent
PriceAgent
OrderAgent
PostgreSQL 基础表
Redis 时间锁
TraceLog 基础记录
```

验收标准：

```text
用户可以输入预约需求
系统可以返回候选方案
用户可以确认预约
订单可以写入数据库
Agent Trace 可以查询
```

---

## 13.2 Phase 2：Harness 工程化增强

目标：

加入可控执行能力。

功能：

```text
Tool Permission
Verification Gate
RiskAgent
Approval Gate
Rollback Manager
Agent Trace 页面
人工审批页面
```

验收标准：

```text
非法工具调用被拒绝
非法预约数据被拦截
高风险订单进入审批
失败时能释放时间锁
后台可以看到执行轨迹
```

---

## 13.3 Phase 3：售后与运营分析

目标：

完善真实业务运营能力。

功能：

```text
CustomerServiceAgent
ReviewAgent
OpsAgent
ChromaDB 知识库
Elasticsearch 搜索
运营分析页面
售后工单页面
```

验收标准：

```text
用户可以申请改期、取消、退款
系统可以生成售后建议
管理员可以查看运营报告
系统可以分析差评原因
```

---

## 13.4 Phase 4：体验优化与部署

目标：

提升系统可用性和展示效果。

功能：

```text
SSE / WebSocket 流式输出
React Flow 工作流可视化
Docker Compose
CI 测试
日志检索
性能优化
```

验收标准：

```text
本地一键启动
前后端联调稳定
核心测试通过
可用于简历展示和面试演示
```

---

## 14. 目录结构建议

```text
massageops-agent/
  backend/
    app/
      main.py
      core/
      api/
      models/
      schemas/
      services/
      repositories/
      agents/
      harness/
      tools/
      tests/
    alembic/
    pyproject.toml
    Dockerfile

  frontend/
    src/
      app/
      pages/
      components/
      features/
        chat/
        orders/
        agent-runs/
        approvals/
        ops/
      api/
      stores/
      types/
    package.json
    Dockerfile

  docker-compose.yml
  README.md
  dev_spec.md
  .env.example
```

---

## 15. Codex 开发执行要求

请 Codex 按以下原则实现：

1. 不要一次性生成所有功能，先完成 Phase 1。
2. 所有业务写操作必须通过 service 层。
3. Agent 不允许直接操作数据库。
4. 所有 Agent 输出必须定义 Pydantic Schema。
5. 所有工具必须注册到 ToolRegistry。
6. 所有工具调用必须经过 PermissionManager。
7. 所有关键业务步骤必须记录 Agent Trace。
8. 预约确认必须使用 Redis 幂等 Key。
9. 排班冲突必须在数据库事务层再次校验。
10. 高风险操作必须进入 ApprovalGate。
11. 前端先实现可用页面，再逐步优化 UI。
12. 每完成一个模块必须补充对应测试。
13. 不要把业务规则写死在 prompt 里，规则应放在 service 或 verification 层。
14. LLM 只负责理解、规划和生成建议，最终业务动作由确定性代码执行。
15. 项目必须可以通过 Docker Compose 本地启动。

---

## 16. Phase 1 具体开发任务

### 16.1 后端任务

1. 初始化 FastAPI 项目。
2. 配置 PostgreSQL 连接。
3. 配置 Redis 连接。
4. 创建 SQLAlchemy models。
5. 创建 Alembic migrations。
6. 实现服务项目、技师、房间、排班、订单基础 CRUD。
7. 实现 IntentAgent。
8. 实现 MatchAgent。
9. 实现 ScheduleAgent。
10. 实现 PriceAgent。
11. 实现 OrderAgent。
12. 实现基础 LangGraph。
13. 实现 HarnessOrchestrator。
14. 实现 ToolRegistry。
15. 实现 TraceLogger。
16. 实现自然语言预约接口。
17. 实现用户确认预约接口。
18. 实现 Agent Trace 查询接口。
19. 编写 Phase 1 测试。

### 16.2 前端任务

1. 初始化 React + TypeScript 项目。
2. 创建 Chat 页面。
3. 创建 MessageBubble 组件。
4. 创建 BookingOptionCard 组件。
5. 创建订单确认组件。
6. 创建 Agent 运行状态展示。
7. 创建 Agent Trace 页面。
8. 对接后端 `/api/v1/conversations/message`。
9. 对接后端 `/api/v1/orders/confirm`。
10. 对接后端 `/api/v1/agent-runs/{trace_id}`。

---

## 17. Phase 1 最小可运行 Demo

### 17.1 Demo 数据

准备以下种子数据：

```text
门店：
- 静心按摩 Tokyo 店

服务：
- 肩颈舒缓 60 分钟，价格 198
- 肩颈舒缓 90 分钟，价格 298
- 全身放松 90 分钟，价格 328

技师：
- 小李，擅长肩颈、力度偏重，评分 4.8
- 小王，擅长放松、力度适中，评分 4.7

房间：
- A101
- A102

排班：
- 小李 今日 18:00-23:00
- 小王 今日 18:00-23:00
```

### 17.2 Demo 输入

```text
今晚8点想约一个90分钟肩颈按摩，预算300以内，力度重一点。
```

### 17.3 期望输出

```text
为你找到一个合适方案：

服务：肩颈舒缓 90 分钟
技师：小李
时间：今晚 20:00 - 21:30
价格：298 元
推荐理由：符合你的预算，技师小李擅长肩颈放松，力度偏重，评分 4.8。

是否确认预约？
```

### 17.4 用户确认后

```text
预约成功。

订单号：order_xxx
服务：肩颈舒缓 90 分钟
技师：小李
时间：今晚 20:00 - 21:30
门店：静心按摩 Tokyo 店
```

---

## 18. 非目标范围

Phase 1 暂不实现：

```text
真实支付
真实短信通知
复杂会员体系
真实地图距离计算
多门店复杂调度
移动端 App
复杂推荐模型训练
```

这些可以在后续阶段扩展。

---

## 19. 成功标准

项目完成后应达到：

1. 可以本地运行。
2. 可以通过聊天完成预约。
3. 可以防止重复预约。
4. 可以看到 Agent 执行轨迹。
5. 可以展示 Harness Engineering 的核心工程思想。
6. 可以作为简历项目和面试项目进行讲解。
7. 后续可以扩展到家政、维修、美甲、宠物护理等其他本地生活场景。

---

## 20. 面试讲解重点

可以这样介绍项目：

```text
这个项目不是普通的多 Agent 聊天 Demo，而是一个面向按摩预约运营场景的可落地智能体平台。我采用 Harness Engineering 思想，在 Agent 外层设计了 Orchestrator、Tool Permission、Verification Gate、Approval Gate 和 TraceLog，保证 Agent 的每一步都可控、可观测、可回滚。

在业务上，系统支持用户通过自然语言预约服务，Agent 会解析用户需求，匹配服务和技师，检查排班冲突，计算价格，进行风控审核，最后在用户确认后创建订单。

在工程上，我没有让大模型直接操作数据库，而是通过工具注册、权限校验和 service 层执行业务动作。这样既能利用大模型的语义理解和任务规划能力，又能保证真实业务系统的稳定性和安全性。
```
