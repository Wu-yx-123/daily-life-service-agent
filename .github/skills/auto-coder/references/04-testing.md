# 测试规范

## 后端测试

运行：

```bash
cd backend
source .venv/bin/activate
python -m pytest app/tests -q
```

测试覆盖重点：

- IntentAgent 输出合同。
- 缺失槽位追问。
- 工具越权拒绝。
- 工具参数沙箱。
- 变更型工具必须在任务沙箱运行。
- 排班冲突。
- 正常预约 API。
- 重复确认幂等。
- Trace 查询。
- 结构化长期记忆写入和召回。
- pgvector 语义记忆写入和相似度召回。
- 记忆清理脚本 dry-run 和 execute 策略。

记忆/pgvector 常用验证：

```bash
cd backend
python -m compileall app scripts
./.venv/bin/alembic heads
./.venv/bin/alembic upgrade head
./.venv/bin/pytest app/tests/test_memory_service.py -q
```

```bash
docker exec dailylifeserviceagent-postgres-1 psql -U massageops -d massageops -c "SELECT extname, extversion FROM pg_extension WHERE extname='vector';"
docker exec dailylifeserviceagent-postgres-1 psql -U massageops -d massageops -c "\\d user_memory_chunks"
```

## 前端测试

运行：

```bash
cd frontend
npm test
npm run build
```

测试覆盖重点：

- 聊天页能发送预约需求。
- 页面显示候选卡片。
- 用户确认后显示预约成功。
- Trace 时间线刷新。

## 规则

- 修改后端业务逻辑必须补 pytest。
- 修改前端交互必须补 Vitest/Testing Library。
- 修改沙箱或权限必须增加拒绝用例和合法用例。
- 修改数据库迁移、pgvector、长期记忆时必须跑 `test_memory_service.py`。
- 修改预约、售后、知识库、审批路径时必须跑 `test_booking_api.py`。
