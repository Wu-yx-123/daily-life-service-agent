# MassageOps-Agent QA Test Progress

## 当前基线

- 后端 pytest：`10 passed`
- 前端 Vitest：`1 passed`
- 前端 build：成功
- 服务健康检查：`8000/docs = 200`，`5173 = 200`

## 已覆盖

- [x] IntentAgent schema
- [x] 缺失槽位
- [x] 工具越权
- [x] 工具参数沙箱
- [x] 变更型工具任务沙箱
- [x] 跨 trace state 拦截
- [x] 排班冲突
- [x] 正常预约 API
- [x] 重复确认幂等
- [x] 前端主路径

## 待补充

- [ ] Playwright 真实浏览器端到端测试
- [ ] Docker Compose 启动后的容器安全检查
- [ ] PostgreSQL 真实并发确认测试
- [ ] Verification Gate 完整测试
