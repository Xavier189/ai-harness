# ai-harness

> 本仓库就是 `ai-harness` 工具自身（dogfood：用 harness 管理 harness）。
> 新 session 先按下方 router 读 `docs/ai-harness/STATE.md`、`CONTEXT.md`、`DECISIONS.md`，即可知道项目是什么、目标、做到哪、下一步。

<!-- AI-HARNESS:ROUTER:START -->
## AI Harness

- 人读说明放在 `docs/ai-harness/`；机器和 phase state 放在 `.harness/`。
- 重要工作开始前读取 `docs/ai-harness/STATE.md`、`docs/ai-harness/CONTEXT.md`、`docs/ai-harness/DECISIONS.md`。
- 任务属于 active phase 时才读取 `.harness/phases/current/PLAN.md`。
- 默认不读 `.harness/phases/archive/**`；需要历史上下文时使用 `harness recall <keyword>`。
- 保持本入口文件短小；稳定 policy 放到 `docs/ai-harness/POLICIES.md`。
- Skill 唯一来源在 `.agents/skills/ai-harness/SKILL.md`（Codex 原生扫描该目录；Claude 经 `.claude/skills/ai-harness` 软链指回）。
- Core profile 已启用；项目专属技术 policy 可追加到 `docs/ai-harness/POLICIES.md`。
<!-- AI-HARNESS:ROUTER:END -->

## Cursor Cloud specific instructions

- 本仓库是单文件、**零运行时依赖**的 Python 3.9+ CLI（`ai_harness.py`）；无需安装第三方包，无独立 lint 配置（CI 不跑 lint）。
- dev/test/build/run 命令以 `README.md` 的「开发」节与 `.github/workflows/ci.yml` 为准：
  - 测试：`python3 -m unittest discover -s tests`
  - 行为场景 eval：`python3 evals/run.py`
  - 自检闸门：`python3 ai_harness.py check`（有 error 退出码非 0）；改动 harness 相关文件后务必跑一遍。
- `harness` / `ai-harness` 命令通过 `pip install -e .` 装到 `~/.local/bin`（已在 `~/.bashrc` 把该目录加入 PATH）；新 shell 即可直接用 `harness ...`，等价于 `python3 ai_harness.py ...`。
- `harness recall <kw>` 只检索 `.harness/phases/archive/**` 与 `.harness/memory/**`；当前 active phase（`current/`）里的内容不会被 recall 命中，属预期行为。
