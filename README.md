# MassageOps-Agent

> Repository: daily-life-service-agent

基于 FastAPI + PostgreSQL + Redis + LangGraph + React 的智能按摩预约运营平台。

## 技术栈

| 层 | 技术 |
|---|---|
| 后端框架 | FastAPI + Python 3.11 |
| 数据库 | PostgreSQL 16（asyncpg 驱动） |
| 缓存/锁 | Redis 7 |
| Agent 编排 | LangGraph + 自研 Harness Orchestrator |
| LLM | Qwen-plus（兼容 OpenAI API） |
| 知识库 | 外部 MCP RAG Server |
| 前端 | React 19 + TypeScript + Vite 6 |
| 部署 | Docker Compose |

## 快速启动

```bash
docker compose up -d
```

- 前端：http://localhost:5173
- 后端 Swagger：http://localhost:8000/docs

启动后自动执行：alembic 数据库迁移 → Demo 数据种子 → 启动 FastAPI。

登录方式：
- **顾客**：demo_user_001（选择"我是顾客"）
- **商家**：merchant_001（选择"我是商家"→管理后台）

## 本地开发

```bash
cd backend
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[test]"

# 需要先启动 PostgreSQL 和 Redis（可复用 Docker）
docker compose up -d postgres redis

# 数据库迁移
alembic upgrade head

# 写入 Demo 数据
python scripts/seed_demo_data.py

# 启动后端
uvicorn app.main:app --reload --port 8000
```

```bash
# 前端
cd frontend && npm install && npm run dev
```

## 数据库

仅支持 PostgreSQL，通过 Alembic 管理迁移：

```bash
# 迁移到最新
alembic upgrade head

# 生成新迁移
alembic revision --autogenerate -m "描述"

# 重置（清空 + 迁移 + 种子）
python scripts/reset_demo_data.py
```

## 测试

```bash
# 创建测试数据库（首次）
docker exec dailylifeserviceagent-postgres-1 psql -U massageops -c "CREATE DATABASE massageops_test;"

# 运行测试
MASSAGEOPS_TEST_DATABASE_URL=postgresql+asyncpg://massageops:massageops@localhost:5432/massageops_test pytest app/tests/ -v
```

全部 39 个测试针对真实 PostgreSQL 运行，覆盖：
- 预约完整闭环 + Trace
- 幂等确认防重
- 高风险订单审批流
- 售后工单创建
- 评价分析 → 运营报表
- 知识库查询
- 工具权限沙箱 + 任务隔离
- 排班冲突检测
- VerificationGate 全部 5 层校验

## 项目结构

```
backend/
  app/
    agents/          # 11 个 Agent（Intent/Match/Schedule/Price/Risk/Order/CS/Review/Ops/Knowledge/Planner）
    harness/         # 工程控制层（Orchestrator/Verification/Permission/Sandbox/Trace/Rollback/Approval）
    tools/           # 7 组工具（22 个工具函数）
    services/        # 业务服务层
    repositories/    # 数据访问层
    models/          # 16 个 ORM 模型
    schemas/         # Pydantic contracts
    api/v1/routes/   # 10 组 REST API
  alembic/           # 4 个迁移文件
  scripts/           # seed / reset / docker_entrypoint
  tests/             # 39 个 pytest 用例
frontend/
  src/
    features/        # chat / admin / auth / approvals / ops
    api/             # API client
    app/             # 入口 + 角色路由
docker-compose.yml   # 4 服务编排
```

## Agent LLM 接入状态

| Agent | 策略 |
|---|---|
| IntentAgent | LLM 主力（qwen-plus）→ 正则回退 |
| CustomerServiceAgent | LLM + 知识库政策 → 规则回退 |
| ReviewAgent | LLM 语义理解 → 关键词回退 |
| KnowledgeAgent | MCP RAG Server → SQL 回退 |
| Match/Schedule/Price/Order/Risk/Planner/Ops | 确定性规则（正确选择） |
