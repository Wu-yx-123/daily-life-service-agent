# Agent 记忆机制

## 一句话总结
基于 Redis SessionStore + 多轮对话历史 + AgentState 持久化，实现跨轮上下文保留，让系统理解"换成明天同一时间"中的"同一时间"指代上一轮的 20:00。

## 三层记忆体系

```
第 1 层：会话级短记忆（Redis, TTL 2h）
  └─ SessionStore: 消息历史 List + AgentState JSON
  └─ 最近 10 轮对话注入 LLM 上下文

第 2 层：多轮状态持久化（AgentState cross-turn）
  └─ selected_option / task_type / order_draft 跨轮保留
  └─ "换成明天同一时间" → 读上次的 20:00 → 01/01 20:00

第 3 层：长期画像（PostgreSQL user_profiles，待实现）
  └─ 偏好服务、技师、时间段、消费习惯
```

## 核心实现

### SessionStore (`app/core/session_store.py`)
```python
# 消息历史 → Redis List
await session_store.append_message(sid, "user", "今晚8点肩颈按摩")
await session_store.append_message(sid, "assistant", "已为你找到方案...")

# 状态持久化 → Redis String (JSON)
await session_store.save_state(sid, agent_state)

# 下次请求恢复
history = await session_store.recent_messages(sid, n=10)     # 最近10轮
last_state = await session_store.get_last_state(sid)         # 上次 selected_option
```

### IntentAgent 上下文注入
```python
# LLM 看到完整对话历史
messages = [system_prompt]
for h in history[-6:]:
    messages.append(ChatMessage(role=h["role"], content=h["content"]))
messages.append(ChatMessage(role="user", content=f"当前输入：{message}"))
```

### Orchestrator 状态合并
```python
# 跨轮保留关键字段
for key in ("selected_option", "candidates", "task_type", "order_draft"):
    if key in last_state:
        state[key] = last_state[key]
```

## 效果对比

| 场景 | 无记忆 | 有记忆 |
|---|---|---|
| "换成明天同一时间" | ❌ "同一时间"=null | ✅ 06/01 20:00 |
| "小李可以吗" | ❌ 不知道候选方案 | ✅ 上下文有 selected_option |
| "算了退款吧" | ❌ 新 session | ✅ 任务类型正确切换 |

## 面试重点

**Q: 多轮对话记忆怎么实现的？**
A: Redis SessionStore 存消息历史 List + AgentState JSON，TTL 2h。每次请求恢复上次的 selected_option / task_type / order_draft，IntentAgent 的 LLM 上下文注入最近 6 轮对话。这样"换成明天同一时间"能正确解析为预约改期 + 明天 20:00。

**Q: 为什么用 Redis 而不是 PostgreSQL？**
A: 会话记忆是热数据，TTL 2h，Redis 天然适合。长期画像（用户偏好、消费习惯）才落 PostgreSQL。这也符合"热数据 Redis + 冷数据 PG"的常见分层。
