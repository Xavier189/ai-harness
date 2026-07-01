# 有效决策

本文只索引仍然约束项目的 decision。

| ID | Decision | Source |
|---|---|---|
| HD-0001 | 人读 `docs/` 分层 vs 机器 `.harness/`。 | Harness initialization |
| HD-0002 | 零运行时依赖（仅 Python3 标准库），不引框架。（原含"单文件"，已由 HD-0007 拆分/降级） | v0.1 / ADR-0001 |
| HD-0003 | 新增能力一律可选、可回退、不增加每次启动加载量。 | 贯穿原则 |
| HD-0004 | `schemaVersion` 表示生成布局契约代数，由 `upgrade` 演进；当前=2。 | VERSIONING.md |
| HD-0005 | 取其精华、弃其糟泊：不抄 enterprise ceremony、不默认强制 TDD、不做框架膨胀。 | docs/REVIEW-AND-ROADMAP.md |
| HD-0006 | 本仓库 dogfood：用 harness 管理 harness 自身。 | 自举 |
| HD-0007 | 红线重定义：真红线=零依赖 + 不增启动负担 + 可选可回退 + 装/用零摩擦；**单文件降级**为默认 guardrail（有逃生口，不得单独作为拒功能理由）。 | ADR-0001 |

历史或已被取代的 decision 应进入 phase archive 或 `docs/adr/`，不放在本索引。
