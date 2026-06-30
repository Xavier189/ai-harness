# ai-harness

> 本仓库就是 `ai-harness` 工具自身（dogfood：用 harness 管理 harness）。
> 新 session 先按下方 router 读 `docs/ai-harness/STATE.md`、`CONTEXT.md`、`DECISIONS.md`，即可知道项目是什么、目标、做到哪、下一步。

<!-- AI-HARNESS:ROUTER:START -->
## AI Harness

- 人读说明放在 `docs/ai-harness/`；机器和 phase state 放在 `.harness/`。
- 重要工作开始前读取 `docs/ai-harness/STATE.md`、`docs/ai-harness/CONTEXT.md`、`docs/ai-harness/DECISIONS.md`。
- 任务属于 active phase 时才读取 `.harness/phases/current/PLAN.md`。
- 默认不读 `.harness/phases/archive/**`；需要历史上下文时使用 `harness recall <keyword>`。
- 保持本入口文件短小；稳定 policy 放到 `docs/ai-harness/POLICIES.md`。
- Skill 唯一来源在 `.agents/skills/ai-harness/SKILL.md`（Codex 原生扫描该目录；Claude 经 `.claude/skills/ai-harness` 软链指回）。
- Core profile 已启用；项目专属技术 policy 可追加到 `docs/ai-harness/POLICIES.md`。
<!-- AI-HARNESS:ROUTER:END -->
