# Evidence: harden-state-check-version

在这里记录 verification command、重要输出和未解决风险。

## 验证（真实输出，2026-07-01）

```
$ python3 -m unittest discover -s tests
Ran 46 tests in 0.439s
OK                                  # 40 原有 + 6 新增（N1/N2/N3/N4）

$ python3 evals/run.py
5/5 场景通过

$ python3 ai_harness.py check
check: 0 error(s), 0 warning(s)

$ python3 ai_harness.py --version
harness 0.8.0                       # 与 __version__ 单一来源一致

$ python3 -c "import ai_harness; print(ai_harness.__version__)"  → 0.8.0
pyproject dynamic = ['version'] | attr = ai_harness.__version__   # 漂移消除
```

### N1 + startedAt（dogfood 真库实测）

`phase checkpoint --status verify` 后 state.yml：
- `status: discover → verify`（定点字段确实更新）
- `startedAt` 保持 `2026-07-01T02:09:05+00:00` **不变**（旧代码会刷成当前时间）
- `limits`、`context.requiredRead`、`currentPath` **全部保真**（旧代码全量重渲染会抹掉）
- 单测 `test_update_state_preserves_user_limits_and_context` 另测：自定义 limits=999 + 追加 GLOSSARY.md 必读项后仍保真。

### N2

state.schemaVersion 改成 1 后 `check` 报 warning「schemaVersion 1 ≠ 当前 2，运行 `harness upgrade --apply` 对齐」，退出码 0（不拦 CI）；`upgrade --apply` 后 warning 消失。config.yml 同校验。

### N3

limits 阈值写成 `abc` 后 `check` 不再 ValueError 崩溃，报 warning「非整数，回退默认」，退出码 0。

### N4

`__version__ = "0.8.0"` 单一来源；docstring 去掉写死版本；`--version` 生效；pyproject `dynamic=["version"]` 读该常量；README 开发节 36/4 → 40/5。

## Verify Checklist（收尾前逐条过，不适用标 N/A）

- [x] 失败路径已验证：N3 非数字 limits fail-closed 回退；N2 落后版本降级为 warning 不拦 CI。
- [x] 多视角已过：运维（--version 查版本、check 提示 upgrade 路径）；安全合规（无 secret / payload 泄露）。
- [x] 异常归宿点：N3 非数字只报一条 warning，不抛栈。
- [x] 对外契约变更已告知下游：README §5 校验声明本已存在，本次是兑现（补齐而非新增契约）；--version 为新增只读命令。
- [x] 端到端验证有真实输出，非"看起来好了"（见上）。

## Checkpoint 2026-07-01T02:36:59+00:00

- Status: `verify`
- Note: N1/N2/N3/N4 全部落地：46 tests OK + evals 5/5 + check 0 error + --version 0.8.0；本次 checkpoint 即 dogfood 验证新 update_state
