# 项目概述

MassageOps-Agent 是一个按摩/SPA/理疗等本地生活服务场景的多 Agent 智能预约与运营平台。

当前代码已完成 Phase 1 MVP：

- FastAPI 后端
- SQLAlchemy 数据模型
- Redis 时间锁与幂等 Key
- LangGraph 基础预约流程
- IntentAgent / MatchAgent / ScheduleAgent / PriceAgent / OrderAgent
- TraceLog
- React 聊天预约页面
- 三层沙箱：Agent 工具权限、任务级隔离、Docker 容器运行

项目目标不是做普通聊天机器人，而是展示 Agent 如何在工程约束下执行真实业务流程。
