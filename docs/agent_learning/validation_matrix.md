# Validation Matrix

本文件定义不同类型改动应该执行的验证命令。

## 通用后端改动

```bash
cd backend
python -m compileall app scripts
./.venv/bin/pytest app/tests -q
```

## 数据库迁移

```bash
cd backend
./.venv/bin/alembic heads
./.venv/bin/alembic upgrade head
```

如果测试库需要重建：

```bash
docker exec dailylifeserviceagent-postgres-1 psql -U massageops -d postgres \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='massageops_test';" \
  -c "DROP DATABASE IF EXISTS massageops_test;" \
  -c "CREATE DATABASE massageops_test;"
```

## 记忆系统

```bash
cd backend
./.venv/bin/pytest app/tests/test_memory_service.py -q
```

覆盖范围：

- 结构化长期记忆写入。
- 强偏好补全安全槽位。
- pgvector 语义记忆写入和召回。
- 记忆清理策略。

## pgvector

```bash
docker exec dailylifeserviceagent-postgres-1 psql -U massageops -d massageops \
  -c "SELECT extname, extversion FROM pg_extension WHERE extname='vector';"

docker exec dailylifeserviceagent-postgres-1 psql -U massageops -d massageops \
  -c "\\d user_memory_chunks"
```

预期：

- `vector` extension 已安装。
- `user_memory_chunks.embedding` 类型为 `vector(1536)`。

## 预约和售后主链路

```bash
cd backend
./.venv/bin/pytest app/tests/test_booking_api.py -q
```

覆盖范围：

- 正常预约和订单确认。
- 重复确认幂等。
- 高风险审批。
- 审批通过后恢复创建订单。
- 售后工单。
- 评价分析和运营报表。
- 知识库政策依据。

## 记忆清理脚本

```bash
cd backend
./.venv/bin/python scripts/prune_memories.py
./.venv/bin/python scripts/prune_memories.py --execute
./.venv/bin/python scripts/prune_memories.py --delete-user --user-id <uuid> --execute
```

默认 dry-run；只有加 `--execute` 才会删除。

## 前端

```bash
cd frontend
npm test
npm run build
```

前端改动后如果启动本地服务，还需要浏览器验证主要交互。
