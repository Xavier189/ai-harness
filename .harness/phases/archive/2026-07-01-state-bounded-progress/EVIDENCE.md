# Evidence: state-bounded-progress

在这里记录 verification command、重要输出和未解决风险。

## 验证（真实输出，2026-07-01）

```
$ python3 -m unittest discover -s tests   → Ran 67 tests OK（64 + 3）
$ python3 evals/run.py                     → 5/5 场景通过
$ python3 ai_harness.py check              → 0 error, 0 warning
```

- `state_doc()`：当前焦点区加「跨版本进度记 ROADMAP.md；本文只保当前状态，phase archive 会重置」。测试断言含 ROADMAP + phase archive。
- `phase_archive`：重置 STATE 后打印「STATE.md 已重置；跨版本进度请确认记在 ROADMAP.md」。测试断言 archive 输出含 ROADMAP。
- POLICIES：加「STATE.md 有界，跨版本进度记 ROADMAP」条目。
- 本仓 ROADMAP.md 补 v0.9/v0.10 行（进度归宿）；STATE.md 瘦身由本 phase archive 用新模板自动完成。
- **自证**：本 phase 结束 archive 时会同时演示新行为（STATE 重置 + 提示）。

## Verify Checklist（收尾前逐条过，不适用标 N/A）

- [x] 失败路径已验证：N/A（纯文档/模板 + 一条 print，无失败路径）。
- [x] 多视角已过：运维（archive 提示避免误以为 STATE 丢数据）；无 secret。
- [x] 异常归宿点：N/A。
- [x] 对外契约变更已告知下游：STATE 语义收敛为"有界当前状态"，进度归 ROADMAP，已写入 POLICIES + state_doc 模板 + 本 README/ROADMAP。
- [x] 端到端验证有真实输出（见上）。

## Checkpoint 2026-07-01T05:40:07+00:00

- Status: `verify`
- Note: 方向2落地：state_doc 指引进度归 ROADMAP + archive 安全提示 + POLICIES STATE-有界条目 + ROADMAP 补 v0.9/v0.10；67 tests OK(+3)/evals 5/5/check 0e0w
