---
name: agent-self-improvement
description: "把 MassageOps-Agent 项目中的新经验、面试亮点、代码审查发现、测试策略和踩坑结论沉淀回 .github/skills 的自我迭代 skill。Use when 用户说“让 agent 自我进化”“沉淀到 skills”“更新项目记忆”“把这次经验写进 skill”“迭代复习/简历/review/测试 skill”，或希望把一次分析转化为下次可复用的规则、题库、简历表达、审查清单时使用。"
---

# Agent Self Improvement

## 目标

把一次任务中的可复用经验沉淀到 `.github/skills`，让后续 Agent 在学习、复习、简历、模拟面试、代码审查和测试时更贴合当前项目。

这不是让 Agent 无约束改自己。只有用户明确要求沉淀、迭代或更新 skill 时，才修改 skill 文件。

## 必读

- `references/skill_update_matrix.md`：新经验应该写到哪个 skill。
- `references/evolution_workflow.md`：标准 Learn -> Patch -> Validate 流程。
- `references/EVOLUTION_LOG.md`：记录最近沉淀过的主题，避免重复堆料。
- `docs/agent_learning/lessons.md`：项目级经验库，记录已验证的踩坑、架构规则和实现边界。
- `docs/agent_learning/review_rules.md`：代码审查规则。
- `docs/agent_learning/validation_matrix.md`：按改动类型选择验证命令。

## 工作流

1. 提取经验：从当前对话、源码和用户目标中提炼可复用规则。
2. 判断归属：按 `skill_update_matrix.md` 选择要更新的 skill 和 reference。
3. 区分边界：明确哪些是已实现、哪些是设计目标、哪些是后续规划。
4. 更新文件：优先写入 `references/*.md`，只有触发词或流程变化才改 `SKILL.md`。
5. 同步项目级文档：重要经验写入 `docs/agent_learning`，确保人和 Agent 都能复用。
6. 验证结果：用 `rg` 检查关键词、触发描述和参考内容是否覆盖新主题。
7. 记录日志：更新 `references/EVOLUTION_LOG.md`，写明日期、主题、改了哪些 skill。

## 写入原则

- 写成下次可执行的检查项、题库、话术模板或简历 bullet。
- 不写一次性聊天总结。
- 不把规划说成已完成。
- 不重复大段内容；同一事实只保留在最适合的 reference 中。
- 高风险经验必须带验证方式，例如测试、源码定位或审查清单。

## 常见沉淀目标

- 面试亮点：更新 `resume-writer`、`agent-rag-resume-coach`、`interview-prep`。
- 安全审查：更新 `project-review`。
- 测试策略：更新 `qa-tester`。
- 项目学习路径：更新 `project-learner`。
- 开发流程经验：更新 `auto-coder`。

## 输出要求

完成后简短说明：

- 更新了哪些 skill。
- 新增了哪些可复用能力。
- 是否做了关键词验证。
