# Evolution Log

## 2026-05-31

- 建立 `agent-self-improvement` skill，用于把项目经验沉淀回 `.github/skills`。
- 定义 Learn -> Patch -> Validate 流程。
- 建立 skill 更新路由表，覆盖简历、复习、模拟面试、review、测试、学习和开发流程。

后续每次沉淀经验时，在这里追加主题、更新文件和验证方式。

## 2026-06-01

- 主题：将长期记忆、pgvector 语义记忆、记忆清理脚本的实现经验沉淀为 Learn -> Patch -> Validate 规则。
- 更新文件：
  - `docs/agent_learning/lessons.md`
  - `docs/agent_learning/review_rules.md`
  - `docs/agent_learning/validation_matrix.md`
  - `.github/skills/agent-self-improvement/SKILL.md`
  - `.github/skills/agent-self-improvement/references/skill_update_matrix.md`
  - `.github/skills/agent-self-improvement/references/evolution_workflow.md`
- 验证方式：使用 `rg` 检查 `pgvector`、`user_memory_chunks`、`prune_memories`、`Learn -> Patch -> Validate` 等关键词覆盖。
