---
name: ai-harness
description: 本仓库用 ai-harness 管理 AI 协作上下文与有边界的工作 phase。当需要了解当前任务状态、开始/推进/收尾一个 phase、检索历史决策或归档、或维护 docs/ai-harness 与 .harness 时使用本 skill。保留 CLI、phase、state.yml、AGENTS.md、CLAUDE.md 等技术名词原文。
---

# AI Harness（本仓库）

本仓库已安装 ai-harness：人读规范在 `docs/ai-harness/`，机器 state、当前 phase、archive、check 输出在 `.harness/`。

## 开工前先读

- `docs/ai-harness/STATE.md` — 当前短状态。
- `docs/ai-harness/CONTEXT.md` — 稳定项目地图、领域语言、架构边界。
- `docs/ai-harness/DECISIONS.md` — 仍然有效的 decision 索引。
- 仅当任务属于 active phase 时，再读 `.harness/phases/current/PLAN.md`。
- 默认不读 `.harness/phases/archive/**`；需要历史上下文时用 `harness recall <keyword>`。

## Phase 生命周期

合法 state：`idle, discover, discuss, design, plan, execute, verify, compact, archive`。

```bash
harness status                                   # 看当前 phase
harness phase start <slug>                        # 开一个有边界的 phase
harness phase checkpoint --status <state> --note "<note>"
harness phase compact                             # 收尾前压缩成高保真 handoff
harness phase archive                             # 归档，回到 idle
harness recall <keyword>                          # 从 archive/memory 检索
harness migrate                                   # 既有库旧文件名 -> 新结构（先看 dry-run）
harness check                                     # 校验 harness 卫生
```

> CLI 入口：装好后用 `harness`（`uv tool install ai-harness` 或 `pipx install ai-harness`）；未装可 `uvx --from <repo> ai-harness`，或源码直跑 `python3 ai_harness.py`。

## 规则

- 启动上下文保持短小；稳定 policy 放 `docs/ai-harness/POLICIES.md`，不要堆进 AGENTS.md/CLAUDE.md。
- 完成的 phase 先 compact，再 archive，再开下一个。
- PLAN.md 当 self-contained spec 写：点名文件/接口、写明 out-of-scope、给端到端验证步骤。
- 调研用 subagent fan-out 只回蒸馏摘要；verify 用 fresh-context 对抗式复查（先 spec 合规、再代码质量）。
