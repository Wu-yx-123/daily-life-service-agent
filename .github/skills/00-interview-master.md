# MassageOps-Agent 面试复习总纲

## 30 秒电梯演讲

这个项目不是普通的多 Agent 聊天 Demo，而是一个面向按摩预约运营场景的可落地智能体平台。我采用 **Harness Engineering** 思想，在 Agent 外层设计了 Orchestrator、Tool Permission、Verification Gate、Approval Gate 和 TraceLog，保证 Agent 的每一步都可控、可观测、可回滚。

Agent 不直接写数据库——所有写操作经过 Service 层和 VerificationGate 的 9 道门禁校验。同时设计了 SSE 流式输出让用户实时看到 Agent 执行过程，24 条黄金评测用例量化验证系统稳定性。

## 技术栈速览

```
后端: FastAPI + LangGraph + PostgreSQL + Redis + Docker
Agent: 11 个专业 Agent（3 个接 LLM/qwen-plus）
工程: HarnessOrchestrator + 9 Verification Gates + 22 ToolSpec
知识: MCP RAG Server（外部 Agentic RAG）
前端: React 19 + TypeScript + Vite 6 + SSE streaming
测试: 39 pytest + 24 eval + 并发压测
数据库: 16 ORM 模型 + 7 Alembic 迁移
```

## 四大核心亮点

### 1. Multi-Agent 协同 → `01-multi-agent-collaboration.md`
- 11 Agent + 14 LangGraph 节点 + 条件路由
- AgentState 共享内存通信
- Orchestrator 负责数据注入，Agent 不互相调用

### 2. Agent 记忆机制 → `02-agent-memory.md`
- Redis SessionStore：消息历史 + 状态持久化
- 多轮上下文注入 LLM（最近 6 轮）
- "换成明天同一时间" → 正确解析 06/01 20:00

### 3. 权限与沙箱 → `03-permission-sandbox.md`
- ToolSpec 22 工具元数据 + 五层治理链
- PermissionManager 白名单 + 越权审计
- AgentToolSandbox + TaskIsolationSandbox + Docker 三层隔离

### 4. 自我迭代 → `04-eval-iteration.md`
- 24 条黄金评测 + 12 项指标 + 100% 通过率
- 39 pytest + 并发压测（20并发→1订单）
- Alembic 7 迁移，PostgreSQL 真实环境

## 常见面试追问

**Q: 项目有什么实际业务价值？**
A: 按摩/SPA/理疗等本地生活服务行业的预约系统。自然语言输入"今晚8点肩颈按摩，力度重一点" → 自动匹配服务、技师、房间、时间 → 价格计算 → 风控审核 → 订单创建。覆盖售后取消/改期/退款/投诉全流程。

**Q: 和直接用 LangChain 做 Agent 有什么区别？**
A: LangChain 是让 Agent 自由调用工具，适合 Demo 但不适合业务落地。我的项目用 Harness Engineering——Tools 必须注册 ToolSpec，每次调用经过权限、沙箱、超时、审计四层控制。Agent 输出经过 VerificationGate 校验才进入下一步。最终写入由 Service 层的事务复查兜底。

**Q: 部署方式？**
A: Docker Compose 一键启动——PostgreSQL + Redis + Backend + Frontend 4 容器。Alembic 迁移自动执行，Demo 数据自动种子。

## 快速演示脚本

```bash
# 启动
docker compose up -d
# 打开 http://localhost:5173
# 顾客登录: demo_user_001
# 商家登录: merchant_001

# 测试 SSE 流式预约
curl -N -X POST http://localhost:8000/api/v1/conversations/message/stream \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"demo","user_id":"00000000-0000-0000-0000-000000000001","message":"明天20点想约肩颈按摩60分钟"}'

# 运行评估
cd backend && python -m evals.runner --dataset all

# 运行测试
MASSAGEOPS_TEST_DATABASE_URL=postgresql+asyncpg://localhost:5432/massageops_test pytest app/tests/ -v
```
