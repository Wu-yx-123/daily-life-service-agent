# 自我迭代：评估体系 + 黄金评测集

## 一句话总结
从"能跑"升级到"能量化证明稳定"——24 条黄金评测用例覆盖意图识别、预约工作流、售后处理、RAG 检索 4 个维度，12 项评估指标，全部在真实 PostgreSQL 上运行。

## 评估体系结构

```
evals/
  datasets/
    intent_golden.json          # 10 条意图识别
    booking_workflow_golden.json # 5 条工作流
    after_sales_golden.json      # 4 条售后
    rag_retrieval_golden.json    # 5 条 RAG 检索
  runner.py                     # 统一评估运行器
  reports/
    latest_eval_report.json     # 最新报告
```

## 评估结果

```
🟢 intent_golden:          10/10 (100%)   accuracy 100% + schema_valid 100%
🟢 booking_workflow_golden: 5/5  (100%)   workflow 100% + approval 100%
🟢 after_sales_golden:      4/4  (100%)   ticket_type 100% + priority 100%
🟢 rag_retrieval_golden:    5/5  (100%)   recall@K 100% + grounding 100%
─────────────────────────────────────────
总计:                       24/24 (100%)
```

## 12 项评估指标

| 指标 | 含义 |
|---|---|
| intent_accuracy | 任务类型分类正确率 |
| slot_extraction_accuracy | 槽位（服务/时间/预算）提取精确率 |
| schema_valid_rate | Pydantic Schema 校验通过率 |
| workflow_completion_rate | 完整工作流完成比例 |
| approval_trigger_accuracy | 风控触发正确率 |
| conflict_detection_rate | 冲突检测准确率 |
| ticket_type_accuracy | 售后工单类型正确率 |
| priority_accuracy | 优先级判断正确率 |
| rag_recall_at_k | RAG 检索召回率@TopK |
| evidence_source_match | 证据来源匹配率 |
| policy_grounding_accuracy | 政策引用正确率 |

## 并发压测验证

```
20 并发确认 → 1 订单创建 + 19 幂等拦截
三道防线验证：
  ✅ 第 1 层：幂等 Key（idempotency_key nx=True）→ 19 次返回 duplicate
  ✅ 第 2 层：时间锁（Redis SET NX）→ 时段占用后不可再预约
  ✅ 第 3 层：DB 事务复查（OrderService 冲突查询）→ 重复插入抛 ValueError
```

## 面试重点

**Q: 你怎么证明你的 Agent 系统是稳定的？**
A: 24 条黄金评测用例覆盖 4 个核心维度，12 项指标量化评估。全部在真实 PostgreSQL 上运行，不是 mock。另外 39 个 pytest 用例覆盖预约闭环、审批流、售后工单、工具权限、沙箱隔离。还有 20 并发的幂等压测——证明同一时段只创建 1 个订单。

**Q: 黄金评测集怎么设计的？**
A: 每个用例有明确的 input + expected + 可量化判定标准。intent_golden 验证 LLM 的语义理解和槽位提取，booking_workflow 验证完整工作流的 response_type 和中间状态，after_sales 验证工单类型和优先级，rag_retrieval 验证召回率和来源匹配。跑一次评估 90 秒，出完整报告。
