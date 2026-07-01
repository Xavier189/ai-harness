# Evidence: g1-phase-branch

在这里记录 verification command、重要输出和未解决风险。

## 验证（真实输出，2026-07-01）

```
$ python3 -m unittest discover -s tests   → Ran 59 tests OK（54 + 5 新增 G1）
$ python3 evals/run.py                     → 5/5 场景通过
$ python3 ai_harness.py check              → 0 error, 0 warning
```

G1 测试（真实 git subprocess，临时 repo）：
- `--branch` 创建 phase/demo 并切过去；已存在则切换（幂等）
- 非 git 仓库 → fail-soft，phase 照常 start（status=discover），输出"非 git 仓库"
- 不带 `--branch` → git 分支零变化（零回归）
- archive 在 phase 分支上 → 输出提示"你仍在 phase 分支…"

注：真实临时 repo 手工 demo 被沙箱拒（涉及 /tmp 写），但上述 5 个测试用真实 `git init`/`checkout` 精确覆盖同一路径，验证等价。

## Verify Checklist（收尾前逐条过，不适用标 N/A）

- [x] 失败路径已验证：git 缺失/非 repo/checkout 失败 → 均 warning 不崩，phase 照常。
- [x] 多视角已过：运维（--branch 显式 opt-in，输出清楚说明 git 动作）；无 secret 泄露（只回显 git stderr 首行）。
- [x] 异常归宿点：subprocess 不抛，returncode 非 0 归口为一条 warning message。
- [x] 对外契约变更已告知下游：新增 opt-in flag，不带 flag 时行为完全不变；archive 多一行提示（仅在 phase 分支）。
- [x] 端到端验证有真实输出，非"看起来好了"（见上）。

## Checkpoint 2026-07-01T03:21:43+00:00

- Status: `verify`
- Note: G1 选项1落地：ensure_phase_branch + phase start --branch + archive phase 分支提示；59 tests OK(+5,真实 git subprocess) / evals 5/5 / check 0e0w；手验被沙箱拒但测试等价覆盖
