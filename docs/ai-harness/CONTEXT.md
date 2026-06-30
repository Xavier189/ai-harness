# 项目上下文

## 项目

- Name: `ai-harness`
- 用途：一套**轻量、单文件、零依赖**的仓库级 AI 协作 harness。一键给新/旧项目装上「人读 docs / 机器 `.harness` 分层 + 有界 phase + compact→archive→recall」骨架，让 AI agent 跨 session 可恢复、上下文不膨胀。
- 本仓库即工具自身（**dogfood**：用 harness 管理 harness）。

## 核心理念（不可动摇）

1. **人读 `docs/` vs 机器 `.harness/` 分层**，由 `harness check` 强制。
2. **有界上下文**：工作落在一个 phase；完成后 compact→archive，默认不再加载，靠 `recall` 检索。
3. **可暂停/可恢复**：`state.yml` 是 phase 机器 source of truth；checkpoint/HANDOFF 让任意 session「继续」。
4. **可选、可回退、不增加每次启动加载量**；单文件零依赖不变。

## 架构地图

- `ai_harness.py` — 单文件 Python3 CLI（约 1440 行）：全部生成逻辑/命令/校验都在此，零运行时依赖（仅标准库）。`pyproject.toml` 把它暴露为 `harness` 命令。
- `tests/` — unittest（40 tests）；`evals/` — 声明式行为场景 runner（5 场景）。
- `skills/ai-harness-init/` — 给「要安装本 harness 的项目」用的 meta-skill。
- `.agents/skills/ai-harness/` — skill 唯一真实来源（同时是 Codex 原生扫描目录）；`.claude/skills/ai-harness` 软链指回。
- `docs/`、`VERSIONING.md` — 评审依据与版本治理。
- `todo/` — 前瞻计划（`v0.5-plan` / `backlog` / `multi-tool-roadmap`）。
- 临时 phase 工作放在 `.harness/phases/current/`，不要写进本文。

## 设计 ← 参考来源（取其精华）

| 设计 | 来源 |
|---|---|
| 分层、有界上下文、最小高信号 token、语义化 compact、sub-agent 蒸馏摘要 | Anthropic Context Engineering |
| router 短入口、领域知识进 skills、hook 闸门、对抗复查、self-contained spec | Claude Code Best Practices |
| state=source of truth、pause/resume、unify state、small agents | 12-Factor Agents |
| skill 自动触发、brainstorm→plan→execute、两阶段对抗复查、用 eval 测 skill | obra/Superpowers |
| numbered phases + scope、干净上下文 per task、out-of-scope 一等、versioning | gsd-core |
| 工程基线四原则/失败路径优先/异常归宿点、结构化 memory、ADR | 母本 pf-custom-service |

## Context Loading

- 重要工作开始前读取本文 + `STATE.md` + `DECISIONS.md`。
- 项目全景与实现原理见根 `README.md`；评审依据见 `docs/REVIEW-AND-ROADMAP.md`。
- 不要把 session transcript 或 implementation log 追加到本文。
