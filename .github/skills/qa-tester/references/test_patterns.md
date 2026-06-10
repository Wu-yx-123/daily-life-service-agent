# 测试模式

## 后端

使用 PostgreSQL + InMemoryRedis 做快速单元/集成测试。pgvector 相关测试需要 `vector` 扩展。

关键 fixture：

- `db_session`
- `memory_lock_store`
- `client`

新增后端测试时优先放在：

- `backend/app/tests/test_booking_api.py`
- `backend/app/tests/test_schedule_service.py`
- `backend/app/tests/test_sandbox.py`
- `backend/app/tests/test_memory_service.py`

记忆系统测试模式：

- 结构化长期记忆：确认预约后查 `MemoryRepository.list_user_preferences`。
- 强偏好补全：构造 `defaults`，调用 `MemoryService.apply_to_intent`。
- pgvector 语义记忆：调用 `SemanticMemoryService.record_booking_memory` 后再 `retrieve_for_user`。
- 记忆清理：构造过期弱记忆和强记忆，验证 `MemoryRetentionService.prune_stale_memories` 只删弱记忆。
- 测试库每次 `create_all` 前要执行 `CREATE EXTENSION IF NOT EXISTS vector`。

## 前端

使用 Vitest + Testing Library。

Mock `fetch` 覆盖：

- `/api/v1/conversations/message`
- `/api/v1/orders/confirm`
- `/api/v1/agent-runs/{trace_id}`

## Docker

静态检查 `docker-compose.yml`：

- `read_only: true`
- `cap_drop: ALL`
- `security_opt: no-new-privileges:true`
- `tmpfs`
