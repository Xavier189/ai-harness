# Roadmap

项目级规划：numbered phases + backlog。active phase 细节在 `.harness/phases/current/PLAN.md`，不要写进本文。

## Phases

| # | Phase | 目标（一句话） | 状态 |
|---|---|---|---|
| 0 | bootstrap | v0.1 基线 + 自举（dogfood） | done |
| 1 | v0.2 | 闸门/正确性（A1/B1/B3/C1/D1） | done |
| 2 | v0.3 | 体验/智能（A2/B2/B4/C2/C3/D2/D3/D4） | done |
| 3 | v0.4 | `.agents` 唯一来源 + Claude 软链（多工具适配地基） | done |
| 4 | v0.5 | 打磨/演进（D6/B5/B6/D5/C4） | done |
| 5 | v0.6 | Codex/AGENTS.md 单文件引用 skill | done |
| 6 | v0.7 | 分发打包：pyproject + console_scripts，`uvx`/`pipx`/`uv tool install` 一行安装 | done |
| 7 | v0.8+ | Cursor / Windsurf / Aider / Gemini 适配（按需顺延） | planned |
| 8 | release | 发布 PyPI（`uvx ai-harness` 免 --from）+ LICENSE / CI / CHANGELOG | planned |

详细：分发与多工具路线见 `todo/multi-tool-roadmap.md`；打磨项见 `todo/v0.5-plan.md`；评审依据见 `docs/REVIEW-AND-ROADMAP.md`。

## Backlog（未排期）

- 见 `todo/backlog.md`：分发安装(H)、平台广度、phase/git 深度、记忆检索、可观测、健壮性、OSS 治理(H)。

## 已归档 Phase

- 见 `.harness/phases/archive/`，用 `harness recall <keyword>` 检索。
