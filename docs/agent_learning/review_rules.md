# Agent Review Rules

本文件沉淀 MassageOps-Agent 的代码审查规则。Review 时优先找业务风险、安全边界、数据一致性和测试缺口。

## 记忆系统

- 短期记忆、结构化长期记忆、语义长期记忆必须边界清晰。
- `SessionStore` 只保存会话级状态，不应承担长期画像职责。
- `user_preferences` 只保存结构化偏好，不应塞完整聊天记录。
- `user_memory_chunks` 必须按 `user_id` 隔离召回，避免跨用户记忆污染。
- 语义记忆只能辅助理解，不代表本轮用户已确认信息。
- `preferred_time` 等强确认字段不能由长期记忆直接补全。
- 订单确认成功前不应写长期记忆。
- 记忆写入失败不能破坏订单确认主链路。
- 隐私删除要同时删除结构化偏好和 pgvector 语义记忆。

## pgvector

- `docker-compose.yml` 应使用带 pgvector 的 Postgres 镜像。
- Alembic migration 必须包含 `CREATE EXTENSION IF NOT EXISTS vector`。
- 测试库 `create_all` 前必须启用 vector 扩展。
- 向量召回查询必须带 `user_id` 条件。
- pgvector 列类型和 embedding 维度要一致，目前为 `vector(1536)`。
- 本地测试不能依赖外部 embedding API，必须有确定性 fallback。

## MCP RAG

- MCP RAG 保存平台共享知识，不保存用户私有长期记忆。
- 知识库检索必须有 SQL fallback 和兜底文案。
- 售后工单建议应稳定带上政策依据；不能依赖 LLM 自己说出固定关键词。
- SQL fallback 的 query 要符合当前轻量关键词检索方式，必要时拆分关键词。

## Agent 编排

- 新增上下文字段时要同时接入标准 `run` 和 SSE `stream_run`。
- 新增高风险增强能力时要有 try/except 降级，避免影响主业务。
- LLM 输出必须经过 Pydantic 合同或 VerificationGate。
- 写操作必须走 service 层，Agent 不直接写数据库。
- 关键业务动作必须可追溯到 trace、order 或 evidence。

## 测试

- 记忆系统至少覆盖：写入、召回、强偏好补全、pgvector 相似度召回、过期清理、用户隐私删除。
- 数据库测试不要并行抢同一个 `massageops_test`，否则 PostgreSQL 元数据可能冲突。
- 每次新增迁移后要跑 `alembic heads` 和 `alembic upgrade head`。
