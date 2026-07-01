# Phase Plan: state-bounded-progress

## Goal（有边界的目标）

落实方向 2：让 STATE.md 成为"有界当前状态"文档——跨版本进度改记 ROADMAP，STATE 不再累积叙述，从而 `phase archive` 用 `state_doc()` 重置 STATE 时**无损**。修掉本 session 暴露的"archive 冲掉 STATE 进度叙述"数据丢失。

## In Scope / 涉及文件与接口

- `ai_harness.py`
  - `state_doc()` 模板：当前焦点区加一行指引「跨版本进度记 `ROADMAP.md`；本文只保当前状态，`phase archive` 会重置」。
  - `phase_archive`：重置 STATE 后打印一句安全提示「STATE.md 已重置；跨版本进度请确认在 ROADMAP」。
  - （POLICIES 模板 `POLICIES.md` 生成函数）加一条短 policy：STATE 有界、进度归 ROADMAP。
- 本仓 dogfood 文档：
  - `docs/ai-harness/STATE.md`：瘦身为当前状态，删「已完成 v0.x 摘要」。
  - `docs/ai-harness/ROADMAP.md`：补 v0.9 / v0.10 行（进度归宿）。
- `tests/`：断言 `state_doc()` 含 ROADMAP 指引；archive 提示（可选）。

## Out of Scope（明确不做）

- 不新增 CHANGELOG 文件（YAGNI；ROADMAP 已是进度归宿，CHANGELOG 留 release backlog）。
- 不改 archive 的"覆盖 STATE"机制本身（方向 1 已否）；只让覆盖无损 + 加提示。
- 不动 compact 的 `short_state_after_compact`（已够短）。

## Tasks

- [ ] state_doc 模板加 ROADMAP 指引
- [ ] phase_archive 加安全提示
- [ ] POLICIES 加 STATE-有界 policy
- [ ] 本仓 STATE 瘦身 + ROADMAP 补 v0.9/v0.10
- [ ] 测试 + 端到端验证
- [ ] compact 并 archive

## 端到端验证（End-to-End Verification）

    python3 -m unittest discover -s tests          # 期望 OK
    python3 ai_harness.py check                    # 0 error（STATE 瘦身后仍合规）
    python3 evals/run.py                           # 5 场景全过

## Acceptance Criteria

- state_doc 指引进度归 ROADMAP；archive 打印安全提示；POLICIES 有对应条目。
- 本仓 STATE 瘦身、ROADMAP 记录 v0.9/v0.10。
- `check` 0 error；本 phase 有清晰 handoff。
