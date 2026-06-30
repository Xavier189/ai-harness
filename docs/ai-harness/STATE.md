# 当前状态

项目：`ai-harness`（独立仓库，已从 pf-custom-service 剥离）

## Phase

- Status: `idle`
- Current phase: 无
- Next action: 开工下一项时运行 `harness phase start <slug>`（路线见 `docs/ai-harness/ROADMAP.md`）。

## 当前焦点

- 已完成 v0.1 基线 + v0.2 + v0.3 + v0.4 + v0.5 + v0.6；schemaVersion **2**；`python3 -m unittest discover -s tests` → **40 tests OK** + `evals/` 5 场景全过。
- 本仓库已**自举**（dogfood）：根目录有 `CLAUDE.md`/`AGENTS.md` router + `docs/ai-harness` + `.harness` + `.agents/skills`（唯一来源）+ `.claude/skills`（软链），新 session 可带记忆冷启动。

## 已完成（摘要）

- **v0.2**：工程基线进 POLICIES、check 修链接/去重、`migrate`、skill 装入、PLAN 自包含 spec。
- **v0.3**：EVIDENCE verify checklist、语义化 compact、`upgrade`+VERSIONING、可选 Stop hook、subagent 协作 policy、ROADMAP、ADR 模板、结构化 memory。
- **v0.4**：`.agents/skills/` 设为唯一真实来源，`.claude/skills` 改目录软链；软链不可用回退副本 + check 校验。
- **v0.5**：D6 收敛 current/ 冗余、B5 强化测试 + `evals/`、B6 lessons 阈值 check、D5 OUT-OF-SCOPE、C4 `--with-commands`。
- **v0.6**：AGENTS.md/CLAUDE.md ROUTER 指明 skill 唯一来源；确认 Codex 原生扫描 `.agents/skills/`。
- **v0.7**：分发打包——`pyproject.toml` + console_scripts（单文件模块 `ai_harness.py`），支持 `uv tool install` / `pipx install` / `uvx --from` 一行安装，`harness` 进 PATH（实测通过）。
- **v0.8**：Cursor 适配——Cursor 与 Codex 一样原生扫描 `.agents/skills/`，无需 `.cursor/skills/` 副本；`migrate --apply` 可清理 v0.8 遗留副本。

## 下一步

1. （可选）发布到 PyPI，让 `uvx ai-harness` / `pipx install ai-harness` 免 `--from`；补 CHANGELOG（LICENSE/CI 已就绪）。
2. 适配范围已收敛到 Claude / Codex / Cursor；更多平台暂不做（见 `docs/ai-harness/OUT-OF-SCOPE.md`）。

## 阻塞

- 暂无。

## 验证

- `python3 -m unittest discover -s tests`（40 tests）+ `python3 evals/run.py`（5 场景）。
- 修改 harness 文件后运行 `harness check`（应 0 error）。
