# Phase Plan: harden-state-check-version

## Goal（有边界的目标）

修掉第一轮架构扫描坐实的 4 条内生"名不副实"裂缝 N1/N2/N3/N4，全部在四条红线（单文件 / 零依赖 / 可选可回退 / 不增启动负担）内；做完 `harness check` 0 error、`unittest` + `evals` 全过，且 release 前的版本卫生清零。

## In Scope / 涉及文件与接口

- `ai_harness.py`
  - **N1（方案 A 定点替换）**：新增 `replace_state_fields(text, fields)`；重写 `update_state`，只改 `phase.status/slug/startedAt`（及显式传入的 project 字段），**保真** schemaVersion / limits / context / requiredRead。顺带修 `startedAt` 病根：只在 idle→非idle 时打时间戳，checkpoint 保留原值。
  - **upgrade 连带修**：`update_state(root)` 不再靠全量重渲染 bump schemaVersion → 改为显式 `replace_state_fields({"schemaVersion": ...})`（L754 附近）。这样普通 phase 操作不再静默刷版本，N2 的 mismatch 才测得到。
  - **N2**：新增 `check_schema_version(root, state)`——state.yml / config.yml 的 schemaVersion 落后 → **warning**（提示 `harness upgrade`），兑现 README §5。接入 `run_checks`。
  - **N3**：`run_checks` 的 `int(limits)` 抽成 `_limit(...)` 容错：非整数回退默认 + warning（fail-closed）。
  - **N4**：`__version__ = "0.8.0"` 单一来源；docstring 去掉写死 "v0.1"；加 `--version`。
- `pyproject.toml`：`version` 改 dynamic，读 `ai_harness.__version__`（消除 0.7.0 漂移）。
- `README.md`：§开发 "36 单测/4 场景" → "40/5"。

## Out of Scope（明确不做）

- G1 git 集成、G2 numbered-phase 感知、G3 语义 memory、G4 自动 compact 阈值——战略缺口，另行过闸门，本 phase 不碰。
- 不引任何依赖；不动 phase 状态机语义（除 startedAt 修正）；不重构无关代码。
- 不改 state.yml 的 YAML 格式/字段顺序（A 是纯文本定点替换，round-trip 一致）。

## Tasks

- [ ] N1：`replace_state_fields` + 重写 `update_state`（含 startedAt 修正）
- [ ] upgrade：显式 bump schemaVersion（不再依赖 update_state 重渲染）
- [ ] N2：`check_schema_version` 接入 run_checks
- [ ] N3：`_limit` 容错
- [ ] N4：`__version__` / docstring / `--version` / pyproject dynamic / README 数字
- [ ] 补测试：limits 保真、startedAt 保留、schema mismatch warning、非数字 limits 容错、`--version`
- [ ] 端到端验证（见下）
- [ ] compact 并 archive 本 phase

## 端到端验证（End-to-End Verification）

```bash
python3 -m unittest discover -s tests          # 期望 OK（新增用例后 >40）
python3 evals/run.py                           # 期望 5 场景全过
python3 ai_harness.py check                    # 期望 0 error
python3 ai_harness.py --version                # 期望打印 harness 0.8.0
# N1 手验：改 state.yml 的 limits.stateMaxLines=999 + 加自定义 requiredRead，跑一次 phase checkpoint，确认定制仍在、startedAt 不变
```

## Acceptance Criteria

- N1/N2/N3/N4 全部落地并有针对性测试。
- `harness check` 0 error；unittest + evals 全过。
- 本 phase 有清晰 handoff。
