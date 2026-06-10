---
name: qa-tester
description: "MassageOps-Agent 的中文 QA 测试 skill。Use when 用户说“跑 QA”“测试项目”“验证预约流程”“检查前后端”“补测试计划”“回归测试”，或希望针对 FastAPI API、Redis 时间锁、Agent 沙箱、TraceLog、React 聊天页、Docker 配置执行测试和记录结果时使用。"
---

# QA Tester — MassageOps-Agent

## 目标

验证当前项目的预约闭环、沙箱边界、前端交互和容器配置。

## 测试命令

后端：

```bash
cd backend
source .venv/bin/activate
python -m pytest app/tests -q
```

前端：

```bash
cd frontend
npm test
npm run build
```

服务健康检查：

```bash
curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/docs
curl -s -o /dev/null -w '%{http_code}' http://localhost:5173/
```

## QA 范围

- API 正常预约。
- API 重复确认幂等。
- 缺失槽位不创建订单。
- 排班冲突拒绝。
- Trace 步骤完整。
- Agent 越权工具调用拒绝。
- 工具参数注入拒绝。
- 任务沙箱跨 trace 拒绝。
- 前端显示候选卡和 Trace。
- Docker compose 包含安全配置。

## 记录

更新：

- `QA_TEST_PLAN.md`
- `QA_TEST_PROGRESS.md`
- `references/test_patterns.md`
