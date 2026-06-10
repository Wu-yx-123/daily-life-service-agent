# 后续扩展方向

## Verification Gate

为 intent、schedule、price、order draft 增加统一校验结果对象，失败时写 Trace 并返回可解释错误。

## RiskAgent 与 Approval Gate

实现取消次数、退款次数、异常低价、敏感词等风险规则。中高风险订单进入人工审批。

## Rollback Manager

订单创建失败、支付失败、用户取消确认、审批驳回时释放时间锁。

## 售后

CustomerServiceAgent 处理取消、改期、退款申请、投诉，但不能直接退款。

## 运营分析

OpsAgent 查询订单、服务、技师、评价数据，生成经营分析报告。

## 搜索与知识库

后续接入 ChromaDB 和 Elasticsearch，支持服务说明、售后政策、门店规则等知识检索。
