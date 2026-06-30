# 有效决策

本文只索引仍然约束项目的 decision。

| ID | Decision | Source |
|---|---|---|
| HD-0001 | 人读 `docs/` 分层 vs 机器 `.harness/`。 | Harness initialization |
| HD-0002 | 单文件 CLI、零运行时依赖（仅 Python3 标准库），不引框架。 | v0.1 |
| HD-0003 | 新增能力一律可选、可回退、不增加每次启动加载量。 | 贯穿原则 |
| HD-0004 | `schemaVersion` 表示生成布局契约代数，由 `upgrade` 演进；当前=2。 | VERSIONING.md |
| HD-0005 | 取其精华、弃其糟泊：不抄 enterprise ceremony、不默认强制 TDD、不做框架膨胀。 | docs/REVIEW-AND-ROADMAP.md |
| HD-0006 | 本仓库 dogfood：用 harness 管理 harness 自身。 | 自举 |

历史或已被取代的 decision 应进入 phase archive 或 `docs/adr/`，不放在本索引。
