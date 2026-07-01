# Phase Plan: g5-deepen-check

## Goal（有边界的目标）

给 `harness check` 增两条卫生检查——stale phase（活动态开着很久没 checkpoint）+ required sections（PLAN/EVIDENCE 空壳检测），全 warning 级、纯本地零依赖、可回退。做完 `check` 能拦住"phase 忘了推进"和"phase 文件是空壳"两类静默腐化。

## In Scope / 涉及文件与接口

- `ai_harness.py`
  - **`check_stale_phase(root, state, issues)`**：活动态（status ∈ discover/execute/verify… 排除 idle/compact）时，参考时间 = `max(startedAt, PROGRESS.yml 最新 checkpoint.at)`；`now - 参考 > limits.stalePhaseDays`（默认 7，复用 `_limit` 容错）→ warning。时间解析失败 fail-soft 跳过。
  - **`check_required_sections(root, state)`**：status != idle 时查 `current/PLAN.md`、`current/EVIDENCE.md`：① 必备 heading 存在；② 关键 section 未残留模板占位文本 → warning。占位串抽成共享常量，与模板生成函数同源。
  - 两者接入 `run_checks`（在 `check_schema_version` 之后）。
  - 占位符常量：从 `current_plan()` / `evidence_doc()` 抽出判定用的占位片段（如 PLAN Goal「用一句话写清楚」、EVIDENCE「尚未运行」），checker 与模板共享，防漂移。
- `tests/test_harness_cli.py`：新增用例（见验证）。

## Out of Scope（明确不做）

- orphaned archive 检查（→ backlog E，ROI 最低）。
- required sections 的 lifecycle 阶段化——本期只做"结构 + 占位符残留"。
- 阈值以外任何可配置化；不引依赖；不改现有 check 语义；不动 N1–N4 已落地代码。

## Tasks

- [ ] 抽占位符常量（PLAN/EVIDENCE 模板与 checker 共享）
- [ ] `check_stale_phase`（含 PROGRESS.yml checkpoint 时间解析 + fail-soft）
- [ ] `check_required_sections`（heading 存在 + 占位符残留）
- [ ] 接入 `run_checks`
- [ ] 测试：stale 命中/未命中/时间解析 fail-soft/非数字 stalePhaseDays 容错；required 占位符命中/填好后不报/idle 不查
- [ ] 端到端验证
- [ ] compact 并 archive

## 端到端验证（End-to-End Verification）

    python3 -m unittest discover -s tests          # 期望 OK（>46）
    python3 ai_harness.py check                    # 当前 phase PLAN 已填 → 期望不误报 stale/空壳
    python3 evals/run.py                           # 5 场景仍全过
    # stale 手验：state.yml 的 startedAt 改成 10 天前 + limits.stalePhaseDays=7 → check 报 1 warning

## Acceptance Criteria

- 两 checker 落地并有针对性测试；全 warning，`check` 退出码不因它们变 1。
- `harness check` 对"正常填好的活动 phase"零误报（本仓库自测）。
- 本 phase 有清晰 handoff；`check` 0 error。
