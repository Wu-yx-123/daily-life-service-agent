---
name: auto-coder
description: "MassageOps-Agent 的规格驱动自动开发 skill。Use when 用户说“自动开发”“继续开发”“auto code”“按 dev_spec 做下一项”“实现下一个任务”“补测试”“修 Phase 1/Phase 2 功能”，或希望 Codex 按 dev_spec.md、FastAPI、PostgreSQL、Redis、LangGraph、React、Harness Engineering 的现有架构推进开发并运行测试时使用。"
---

# Auto Coder — MassageOps-Agent

## 目标

按 `dev_spec.md` 和当前代码结构推进开发：读规格、找范围、实现、补测试、验证。

默认使用中文说明过程和结果。

## 强制规则

- 不要一次性实现所有 Phase；除非用户明确要求，优先按当前 Phase 边界推进。
- Agent 不直接写数据库，业务写入必须走 service 层。
- 工具调用必须经过 `ToolRegistry`、`PermissionManager` 和 `AgentToolSandbox`。
- 关键业务步骤必须写 Trace。
- 每完成模块必须补测试。
- 后端命令使用 `backend/.venv`。

## 常用命令

后端测试：

```bash
cd backend
source .venv/bin/activate
python -m pytest app/tests -q
```

前端测试：

```bash
cd frontend
npm test
npm run build
```

本地启动：

```bash
cd backend
source .venv/bin/activate
MASSAGEOPS_DATABASE_URL=sqlite+aiosqlite:///./dev.db MASSAGEOPS_REDIS_URL=memory:// uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend
npm run dev
```

## 工作流

1. 阅读 `dev_spec.md` 和相关源码。
2. 判断用户请求属于 Phase 1、Phase 2、Phase 3 还是部署优化。
3. 列出将修改的文件。
4. 实现代码。
5. 补测试。
6. 运行后端/前端验证。
7. 总结改动、测试结果和未完成边界。

## 参考文件

- `references/01-overview.md`
- `references/02-features.md`
- `references/03-tech-stack.md`
- `references/04-testing.md`
- `references/05-architecture.md`
- `references/06-schedule.md`
- `references/07-future.md`
