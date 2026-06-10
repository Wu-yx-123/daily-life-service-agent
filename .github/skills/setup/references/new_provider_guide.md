# 后续 LLM Provider 扩展指南

当前 Phase 1 没有真实 LLM Provider，IntentAgent 使用确定性规则解析中文预约文本。

如果后续接入 OpenAI-compatible Provider：

1. 新增 `backend/app/core/model_provider.py`。
2. 定义统一接口：`parse_intent(message) -> IntentOutput`。
3. 在 IntentAgent 中保留确定性 fallback。
4. 所有 LLM 输出必须经过 Pydantic Schema 校验。
5. 不允许 LLM 直接写数据库或返回可直接执行的 SQL。
6. 工具调用仍必须经过 `ToolRegistry` 和沙箱。

推荐环境变量：

```bash
MASSAGEOPS_LLM_BASE_URL=
MASSAGEOPS_LLM_API_KEY=
MASSAGEOPS_LLM_MODEL=
```
