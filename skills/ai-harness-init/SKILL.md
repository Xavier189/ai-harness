---
name: ai-harness-init
description: Initialize or evolve an AI harness for a repository. Use this when the user asks to create an AGENTS.md/CLAUDE.md harness, initialize project memory, set up phase-based AI workflow files, prevent planning docs from growing without bounds, add Java/Spring harness policies, or install the ai-harness-template CLI in a new or existing project. 输出和生成文档默认使用中文，保留 CLI、profile、phase、state.yml、AGENTS.md 等 English 技术名词。
---

# AI Harness Init

使用本 skill 帮用户通过 `ai-harness-template` CLI 初始化或演进仓库级 AI
harness。

harness 只有一条核心边界：

- 人读规范放在 `docs/`。
- 机器可读 state、当前 phase 文件、archive、check 输出放在 `.harness/`。

默认文案使用中文；`CLI`、`profile`、`phase`、`state.yml`、`AGENTS.md`、
`CLAUDE.md`、`Java/Spring` 等技术名词保留 English 原文。

## Workflow

1. 提问前先检查目标仓库。
2. 既有库若有旧命名 harness 文件（`current-status.md`、`decision-log.md`、`.harness/memory.md` 等），先 `harness migrate`（dry-run 预览，`--apply` 执行）把旧文件 rename 到新结构，再 `init`，以保留旧内容、避免重复文件。
3. 选择 profile：
   - 除非目标仓库明显是 Java/Spring，或用户明确要 Java/Spring policy，否则用 `core`。
   - Java 17+ / Spring Boot 3.x 服务使用 `java-spring`。
4. 选择 agent entry 文件：
   - 同时支持 Codex 和 Claude 时使用 `codex,claude`。
   - 用户只点名某个 agent 时，只使用对应 agent。
5. 运行或建议运行（装好 `harness` 命令后；安装方式见下「Install」）：

```bash
harness init --profile <profile> --agent <agents>
```

6. 运行：

```bash
harness check
```

7. 汇报生成文件，以及 `check` 的 warning/error。

## Install（让 `harness` 进 PATH）

```bash
uv tool install ai-harness        # 推荐：常驻安装，之后任何项目直接 harness
# 或 pipx install ai-harness
# 未安装时一次性运行：uvx --from <repo-or-path> ai-harness init ...
# 源码直跑：python3 /path/to/ai-harness/ai_harness.py init ...
```

## 设计规则

- 不生成业务代码。
- 不把项目专属事实写进可复用模板。
- 不把 phase 进度或生成的 check 输出放到 `docs/`。
- 不把人读 policy 正文放到 `.harness/`。
- `AGENTS.md` 和 `CLAUDE.md` 只做 router；稳定规则放到 `docs/ai-harness/POLICIES.md`。
- `init` 会把 `ai-harness` skill 装到目标库 `.claude/skills/ai-harness/`，供 Claude Code 自动加载；这是预期产物，不要塞进 `docs/` 或 `.harness/`。
- 默认不读 `.harness/phases/archive/**`；需要历史上下文时使用 `harness recall`。

## Commands

按需使用这些命令：

```bash
harness doctor
harness status
harness migrate
harness upgrade
harness phase start <slug>
harness phase checkpoint --status <state> --note "<note>"
harness phase compact
harness phase archive
harness recall <keyword>
harness check
```

合法 phase state：

```text
idle, discover, discuss, design, plan, execute, verify, compact, archive
```

## 输出格式

汇报完成结果时包含：

- 使用的 profile。
- 更新的 agent entry 文件。
- 关键生成目录。
- `harness check` 结果。
- 需要用户关注的 warning。
