# Agent Learning Lessons

本文件记录 MassageOps-Agent 开发过程中可复用的项目经验。每条经验都应来自真实源码、测试或故障修复，避免把规划写成已完成。

## 2026-06-01: 分层记忆体系落地

### Learn

- 短期记忆使用 Redis `SessionStore`，保存最近消息和 `AgentState`，默认 TTL 为 2 小时。
- 结构化长期记忆使用 PostgreSQL `user_preferences`，保存服务类型、力度、预算、技师、常用时段等可解释偏好。
- 语义长期记忆使用 PostgreSQL pgvector `user_memory_chunks`，保存用户私有自然语言摘要。
- MCP RAG Server 与 pgvector 分工不同：MCP RAG 存平台知识库，pgvector 存用户私有语义记忆。
- 订单确认成功后才写长期记忆，避免用户临时咨询污染画像。
- 语义记忆写入失败不应回滚已确认订单，必须作为增强能力降级处理。
- 切换到 `pgvector/pgvector:pg16` 复用旧 volume 时，可能出现 collation version mismatch，可执行 `ALTER DATABASE ... REFRESH COLLATION VERSION`。

### Patch

- 新增数据库能力时要同步修改：ORM model、`app/models/__init__.py`、Alembic migration、repository、service、测试。
- 新增 Agent 上下文能力时要同步接入：`AgentState`、`HarnessOrchestrator.run`、`stream_run`、相关 Agent prompt、确认/恢复路径。
- pgvector 测试库在 `create_all` 前必须执行 `CREATE EXTENSION IF NOT EXISTS vector`。
- 外部 LLM/embedding 不可用时要有确定性 fallback，保证本地测试可运行。

### Validate

- 记忆相关改动至少运行：

```bash
cd backend
python -m compileall app scripts
./.venv/bin/alembic heads
./.venv/bin/alembic upgrade head
./.venv/bin/pytest app/tests/test_memory_service.py -q
```

- 涉及预约确认、售后、知识库或风险链路时追加：

```bash
./.venv/bin/pytest app/tests/test_booking_api.py -q
```

- pgvector 环境检查：

```bash
docker exec dailylifeserviceagent-postgres-1 psql -U massageops -d massageops -c "SELECT extname, extversion FROM pg_extension WHERE extname='vector';"
docker exec dailylifeserviceagent-postgres-1 psql -U massageops -d massageops -c "\\d user_memory_chunks"
```

## 2026-06-01: 记忆生命周期管理

### Learn

- Redis 短期记忆依靠 TTL 自动过期。
- 结构化长期记忆通过 `confidence`、`seen_count`、`last_seen_at` 判断是否是稳定偏好。
- 语义长期记忆通过 `importance`、`created_at` 判断是否值得长期保留。
- 长期记忆需要支持按 `user_id` 隐私删除，适配账号注销或用户数据删除请求。

### Patch

- 清理逻辑应放在 service 层，脚本只负责参数解析和输出。
- 清理脚本默认必须 dry-run，真正删除需要显式 `--execute`。
- 用户删除必须覆盖 `user_preferences` 和 `user_memory_chunks` 两类长期记忆。

### Validate

```bash
cd backend
./.venv/bin/python scripts/prune_memories.py
./.venv/bin/pytest app/tests/test_memory_service.py -q
```
