# 当前状态

项目：`ai-harness`（单文件、零依赖的仓库级 AI 协作 harness；本仓 dogfood）

## Phase

- Status: `idle`
- Current phase: 无
- Next action: 开工下一项时运行 `harness phase start <slug> [--branch]`（路线见 `docs/ai-harness/ROADMAP.md`）。

## 当前焦点

- 已发布至 **v0.10**；`__version__` **0.10.0**（pyproject dynamic 单一来源）；schemaVersion **2**。
- 验证基线：`python3 -m unittest discover -s tests` → **64 tests OK** + `python3 evals/run.py` → 5 场景全过 + `harness check` 0 error。
- 红线已由 **ADR-0001** 重定义：真红线=零依赖 / 不增启动负担 / 可选可回退 / 装用零摩擦；单文件降级为 guardrail（见 DECISIONS HD-0007）。

## 已完成（摘要，早期见 ROADMAP）

- **v0.7**：分发打包 pyproject + console_scripts（`uvx`/`pipx`/`uv tool install`）。
- **v0.8**：Cursor 原生扫 `.agents/skills/`（撤销复制方案）。
- **v0.9 修地基**：`update_state` 定点替换保真用户 limits/context + 修 startedAt 病根（N1）；check 校验 schemaVersion 落后（N2）；limits 非整数 fail-closed（N3）；`__version__` 单一来源 + `--version`（N4）。
- **v0.10**：深化 check（stale phase / PLAN 空壳检测）；G1 `phase start --branch`（opt-in、零依赖、fail-soft）+ archive phase 分支提示；`harness bootstrap`（已有代码仓库首次上下文初始化）+ CONTEXT 未填 nudge。

## 下一步

1. （可选）发布 PyPI（`uvx ai-harness` 免 `--from`）+ CHANGELOG（LICENSE/CI 已就绪）。
2. backlog 候选：orphaned archive 检查（ROI 低）；G1 剩余（持久 `git.autoBranch` / 显式 `--commit` / worktree，ADR-0001 已延后）。
3. 小瑕疵记录：`phase archive` 用 `state_doc()` 覆盖 STATE.md，会冲掉进度叙述——考虑改为保留。

## 阻塞

- 暂无。

## 验证

- `python3 -m unittest discover -s tests`（64）+ `python3 evals/run.py`（5 场景）。
- 修改 harness 文件后运行 `harness check`（应 0 error）。
