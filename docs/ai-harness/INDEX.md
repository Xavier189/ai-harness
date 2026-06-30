# Harness 索引

## 启动文档

- `docs/ai-harness/STATE.md` - 当前短状态
- `docs/ai-harness/CONTEXT.md` - 稳定项目地图
- `docs/ai-harness/DECISIONS.md` - 有效 decision 索引
- `docs/ai-harness/ROADMAP.md` - 项目级 numbered phases + backlog
- `.harness/phases/current/PLAN.md` - 当前 phase plan，仅 active phase 时读取

## Policy 文档

- `docs/ai-harness/POLICIES.md` - 工程 policy
- `docs/ai-harness/OUT-OF-SCOPE.md` - 项目级「明确不做」清单

## 决策记录

- `docs/adr/0000-template.md` - ADR 模板（复制为 `NNNN-<slug>.md` 新建）

## 项目资料（详细）

- `README.md` - 项目全景：设计、各部分实现效果、实现原理、命令产物
- `docs/REVIEW-AND-ROADMAP.md` - 设计依据与参考来源映射
- `VERSIONING.md` - schemaVersion 演进与 upgrade 约定
- `todo/v0.5-plan.md` - v0.5 待执行计划
- `todo/multi-tool-roadmap.md` - 多工具适配版本化路线图
- `todo/backlog.md` - 长远 backlog

## 机器状态

- `.harness/state.yml` - phase state source of truth
- `.harness/checks/latest.json` - 最新 harness check 输出

## Archives

- `.harness/phases/archive/` - phase history，通过 `harness recall` 检索
