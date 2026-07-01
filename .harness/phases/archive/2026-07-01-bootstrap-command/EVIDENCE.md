# Evidence: bootstrap-command

在这里记录 verification command、重要输出和未解决风险。

## 验证（真实输出，2026-07-01）

```
$ python3 -m unittest discover -s tests   → Ran 64 tests OK（59 + 5 新增）
$ python3 evals/run.py                     → 5/5 场景通过
$ python3 ai_harness.py check              → 0 error, 0 warning（本仓 CONTEXT 已填，无 nudge）
```

- `bootstrap`：开 bootstrap-context phase（status→discover）；未 init 时自动 init；已有 active phase 时拒绝（SystemExit）；检测到 pom.xml 且 profile=core → 提示 java-spring。
- `check_context_filled`：init 后 CONTEXT 为模板 → warning「CONTEXT 仍是模板」；填充后消失。防漂移测试断言占位串出现在 `context_doc()`。
- **真实验证**：#1 填好的两个 Yanxi 仓在新 nudge 下 `check` 均 0 warning（对真实内容无误报）。
- **G1 dogfood**：本 phase 用 `phase start bootstrap-command --branch` 创建，实际在 `phase/bootstrap-command` 分支上开发。

## Verify Checklist（收尾前逐条过，不适用标 N/A）

- [x] 失败路径已验证：未 init 自动 init；active phase 拒绝覆盖；detect 无构建文件时 PLAN 写「未检测到」。
- [x] 多视角已过：运维（bootstrap 打印线索 + 下一步引导 + profile 建议）；无 secret。
- [x] 异常归宿点：active phase 冲突归口为一条 SystemExit 提示，不半途写坏 current/。
- [x] 对外契约变更已告知下游：新增 `bootstrap` 子命令 + 一条 check warning；不影响未用 bootstrap 的现有行为。注意——init 后 check 现在会提示 CONTEXT 未填（预期的 nudge）。
- [x] 端到端验证有真实输出（见上）。

## Checkpoint 2026-07-01T05:07:18+00:00

- Status: `verify`
- Note: bootstrap 命令 + check_context_filled nudge 落地；64 tests OK(+5) / evals 5/5 / check 0e0w；真实验证:两 Yanxi 仓填充后无 nudge、G1 --branch 已用于本 phase 开分支
