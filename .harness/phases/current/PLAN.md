# Phase Plan: no-active-phase

## Goal（有边界的目标）

- 用一句话写清楚"做完什么算完成"。

## In Scope / 涉及文件与接口

- 点名将改动的文件、模块、接口（路径具体到可被 subagent 直接定位）。

## Out of Scope（明确不做）

- 列出本 phase 明确不碰的东西，防止范围蔓延。

## Tasks

- [ ] 发现相关事实（必要时 subagent fan-out，只回蒸馏摘要）。
- [ ] 确认关键 decision。
- [ ] 实现或文档化本 phase 的 scoped change。
- [ ] 端到端验证。
- [ ] compact 并 archive 本 phase。

## 端到端验证（End-to-End Verification）

- 写出可运行的验证命令 / 预期信号（test、build、脚本、对比）；完成时贴真实输出，不写"看起来好了"。

## Acceptance Criteria

- 本 phase 有清晰 handoff。
- `harness check` 没有 error。
