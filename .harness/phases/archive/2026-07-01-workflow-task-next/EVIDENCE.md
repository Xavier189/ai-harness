# Evidence: workflow-task-next

在这里记录 verification command、重要输出和未解决风险。

## 验证（真实输出，2026-07-01）

```
$ python3 -m unittest discover -s tests   → Ran 72 tests OK（67 + 5）
$ python3 evals/run.py                     → 5/5 场景通过
$ python3 ai_harness.py check              → 0 error, 0 warning
$ python3 ai_harness.py next               → 打印当前 status + 状态化下一步（本 phase active → checkpoint/compact/archive）
```

- `harness task "<goal>"`：派生 slug（`Fix Login Bug`→`fix-login-bug`；纯中文兜底 `task`）、Goal 预填进 PLAN、active phase 时拒绝。
- `harness next`：idle+CONTEXT模板→bootstrap；idle+已填→task；active→checkpoint；compact→archive。
- `skill_doc()`：重写为完整工作流（init→bootstrap→task→checkpoint→compact→archive + next/recall/check），本仓 SKILL.md 已同步重生成。
- 设计边界：拒绝 spec-kit 式 ceremony / slash 主驱动 / 带依赖引擎（见 PLAN Out of Scope）。

## Verify Checklist（收尾前逐条过，不适用标 N/A）

- [x] 失败路径已验证：task 空目标/纯中文/active 冲突均归口 SystemExit 或兜底；next 未 init 时给 init 指引。
- [x] 多视角已过：运维（next 让"不知道下一步"可自助）；无 secret。
- [x] 异常归宿点：task active 冲突 SystemExit 一次，不半途写 current/。
- [x] 对外契约变更已告知下游：新增 task/next 子命令 + skill 内容更新；phase start 仍存在（task 的底层等价物），零回归。
- [x] 端到端验证有真实输出（见上）。

## Checkpoint 2026-07-01T06:16:21+00:00

- Status: `verify`
- Note: 最小三件落地：current_plan goal 注入 + harness task + harness next + skill 编码完整循环；72 tests OK(+5)/evals 5/5/check 0e0w；本仓 SKILL 已重生成
