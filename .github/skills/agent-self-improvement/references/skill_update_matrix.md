# Skill 更新路由表

## 面试与简历

更新目标：

- `.github/skills/resume-writer/references/project_highlights.md`
- `.github/skills/agent-rag-resume-coach/references/resume_story.md`
- `.github/skills/agent-rag-resume-coach/references/question_bank.md`
- `.github/skills/interview-prep/references/project_knowledge.md`
- `.github/skills/interview-prep/references/question_bank.md`

适用内容：

- 新项目亮点。
- 面试话术。
- 简历 bullet。
- 高频追问。
- 项目边界说明。

## 代码审查

更新目标：

- `.github/skills/project-review/SKILL.md`
- `.github/skills/project-review/references/question_bank.md`
- `.github/skills/project-review/review_progress.md`

适用内容：

- 安全风险。
- 并发一致性风险。
- Agent 权限边界。
- RAG 入库/查询边界。
- Multi-Agent 职责边界。
- 记忆与上下文边界。

## 测试策略

更新目标：

- `.github/skills/qa-tester/SKILL.md`
- `.github/skills/qa-tester/references/test_patterns.md`
- `.github/skills/qa-tester/QA_TEST_PLAN.md`
- `.github/skills/qa-tester/QA_TEST_PROGRESS.md`

适用内容：

- 新增回归测试场景。
- API 主链路测试。
- 并发、幂等、锁、权限拒绝测试。
- RAG fallback 测试。
- 前端交互测试。

## 项目学习

更新目标：

- `.github/skills/project-learner/SKILL.md`
- `.github/skills/project-learner/references/LEARNING_PROGRESS.md`

适用内容：

- 新学习模块。
- 用户薄弱点。
- 推荐学习顺序变化。
- 源码入口补充。

## 开发流程

更新目标：

- `.github/skills/auto-coder/references/*.md`
- `docs/agent_learning/lessons.md`
- `docs/agent_learning/validation_matrix.md`

适用内容：

- 新开发流程。
- 代码生成约束。
- 架构变更步骤。
- 测试与发布步骤。

## 项目级经验库

更新目标：

- `docs/agent_learning/lessons.md`
- `docs/agent_learning/review_rules.md`
- `docs/agent_learning/validation_matrix.md`

适用内容：

- 已验证的项目经验。
- 真实故障和修复方式。
- 跨 skill 复用的审查规则。
- 不适合只放在某一个 skill 下的验证矩阵。

## 默认规则

- 面向用户表达的内容写入复习/简历/面试 skill。
- 面向质量保障的内容写入 review/qa skill。
- 面向项目知识图谱的内容写入 project-learner。
- 跨开发、审查、测试复用的内容同时写入 `docs/agent_learning`。
- 只有当触发词不够覆盖时才改 `SKILL.md`。
