# Versioning

`ai-harness-template` 的版本治理约定。

## schemaVersion

`.harness/state.yml` 与 `.harness/config.yml` 顶部的 `schemaVersion` 表示**生成布局的契约代数**，
不是项目业务版本。当模板新增/调整必备文件或目录结构时递增。

| schemaVersion | 模板里程碑 | 关键变化 |
|---|---|---|
| 1 | v0.1 | 人读 `docs/` vs 机器 `.harness/` 分层、有界 phase、compact/archive/recall、check |
| 2 | v0.2–v0.3 | `.claude/skills/ai-harness/` 安装、`migrate`、自包含 PLAN、工程基线/协作模式 POLICIES、ROADMAP、ADR 模板、结构化 memory、语义化 compact、可选 Stop hook、`upgrade` |

## upgrade

已初始化的库用 `harness upgrade` 对齐到当前模板：

```bash
harness upgrade                          # dry-run 预览
harness upgrade --apply                  # 补齐缺失文件 + bump schemaVersion
harness upgrade --apply --refresh-infra  # 额外刷新纯模板文件（README/SKILL/ADR 模板）
harness upgrade --apply --with-hooks     # 顺带注入 Stop hook
```

规则：

- **只补齐缺失**：已存在的文件默认不动，保护用户内容（STATE/CONTEXT/DECISIONS/INDEX/POLICIES/ROADMAP/memory/active phase）。
- **`--refresh-infra`** 只覆盖 `INFRA_FILES`（纯模板、用户极少手改）：`docs/ai-harness/README.md`、`docs/adr/0000-template.md`、`.claude/skills/ai-harness/SKILL.md`。
- **bump schemaVersion**：`state.yml`/`config.yml` 重写为当前代数，保留 name/profile/agents/status/slug。
- router（AGENTS.md/CLAUDE.md 的 marker block）仅在已存在 router 时刷新，不强加。

## 升级原则

- 加法优先：新增必备文件走 `upgrade` 补齐，不破坏既有内容。
- 破坏性变更（重命名/删除必备文件）必须：①递增 schemaVersion；②在本表记录；③在 `migrate`/`upgrade` 提供迁移路径或 advisory。
- 任何新增能力保持「可选、可回退、不增加每次启动加载量」。
