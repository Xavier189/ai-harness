# Backlog（长远欠缺 / 远期方向）

> 超出当前 v0.2–v0.4 路线图的欠缺项，从「`ai-harness` 作为独立、成熟、可被他人采用的 OSS 项目」视角盘点。
> 未排期；剥离成独立仓库后转 issue tracker。每项标注：为什么需要 / 大致做法 / 优先级（H/M/L）。
> 红线（ADR-0001 重定义）：**零依赖 + 不增启动负担 + 可选可回退 + 装/用零摩擦**；单文件已从红线降级为默认 guardrail（有逃生口，不得单独作为拒功能理由）。

---

## A. 分发与安装（H）—— ✅ v0.7 已落地核心
现状：已加 `pyproject.toml` + console_scripts（单文件模块 `ai_harness.py`），支持 `uv tool install` / `pipx install` / `uvx --from` 一行安装，`harness` 进 PATH。
- [x] 打包：`pyproject.toml` + console_scripts，`uv tool install ai-harness` / `pipx install` 后 `harness` 进 PATH（v0.7 完成，实测 uvx/uv tool install 通过）。
- [ ] 发布到 PyPI，使 `uvx ai-harness` / `pipx install ai-harness` 免 `--from`（需先建 GitHub repo + PyPI 账号）。
- [ ] `harness --version`；语义化版本与 schemaVersion 解耦（H）。
- [ ] 一键安装脚本（curl | sh）作为无 Python 包管理时的回退（M）。

## B. 平台广度（M）—— Cursor ✅ v0.8
现状：Claude Code（软链）+ Codex（`.agents/skills` 原生）+ Cursor（`.agents/skills` 原生）已支持。
- [x] Cursor 适配：原生扫描 `.agents/skills/`（v0.8 完成；初版复制方案已撤销，`migrate` 可清理遗留副本）。
- [ ] Windsurf / Aider / Gemini / VS Code 按需适配（各查 skills 路径 + 软链支持）（M）。
- [ ] 打包成 Claude Code plugin / marketplace 条目（M），对照 Superpowers 的分发方式。
- [ ] subagents 定义（`.claude/agents/`）随 init 可选生成（L）。

## C. phase / git / workflow 深度（H–M）
现状：ROADMAP 是纯文档，CLI 不感知 numbered phases；无 git 集成。
- [ ] CLI 感知 numbered phases：`phase start` 关联 ROADMAP 行、archive 时回写状态（M）。
- [ ] git 集成：phase↔branch 关联、（收窄）显式 commit、（延后）worktree（H）。对照 GSD「每任务一个 commit」、Superpowers using-git-worktrees。
      **红线已解禁**（ADR-0001：单文件不再是拦它的理由；只用 `subprocess` 调 git = 零依赖 ✓，git 缺失/非 repo 须 fail-soft）。
      范围收敛=**选项 1**：仅 phase↔branch（opt-in `--branch`）；auto-commit 收窄成显式 flag（脏树 auto-commit 破坏用户工作树掌控、且难回滚）；worktree YAGNI 延后。
      优先级：红线过闸但 YAGNI 上不紧急（当前手工桥接几秒钟），排在 G5（深化 check）之后。
- [ ] 并行 wave：独立 plan 并行、依赖串行（M）。对照 GSD execute-phase。
- [ ] compact 自动触发阈值（行数/checkpoint 数）而非纯手动（M）。

## D. 记忆与检索（M）
现状：`recall` 是 grep；`memory/topics/` 有目录无机制。
- [ ] 按 topic 组织/写入 memory；recall 排序与聚合（M）。
- [ ] project-level vs user-level memory 分层（L）。
- [ ] 可选语义检索（需引依赖，谨慎；先关键词加权）（L）。

## E. 可观测 / 质量（M）
现状：check 覆盖行数/链接/state/分层。
- [ ] check 增检（**G5 深化 check，ROI 最高**）：stale phase（开很久没 checkpoint）、orphaned archive、required sections 存在性（M）。
      注：schemaVersion 一致性 + limits 容错已在 v0.9 修地基（N2/N3）落地，G5 剩余=stale/orphaned/required-sections。
- [ ] 轻量 metrics：phase 时长、check 命中率（L）。
- [ ] eval 套件长期化（承接 v0.4 B5），形成 harness 行为回归基线（M）。

## F. 健壮性（M）
- [ ] `parse_state` 是手写 YAML 子集解析器，脆弱：换 JSON 后端或加**可选** PyYAML（保零依赖默认）（M）。
- [ ] 多 session 并发写 state.yml 的文件锁（M）。
- [ ] 模板 i18n：当前全中文，独立项目面向英文社区需要英文/多语言模板（M）。对照 GSD 多语言 README。

## G. OSS 治理（H，剥离时必做）
现状：无 LICENSE / CONTRIBUTING / CHANGELOG / CI / .gitignore。
- [ ] LICENSE（选型：MIT，对照 Superpowers/GSD）（H）。
- [ ] 面向外部用户重写 README + 快速上手 + 录屏/示例（H）。
- [ ] CONTRIBUTING、CODE_OF_CONDUCT、SECURITY、issue/PR 模板（M）。
- [ ] CI：push 跑 `python3 -m unittest discover -s tests`（H）。
- [ ] `.gitignore`（`__pycache__/`、`*.pyc`）、CHANGELOG、release tag（H）。

---

## 远期主张（方向性，非清单）
- **harness 自举**：用本工具管理本工具仓库，吃自己的狗粮，作为活文档与回归。
- **保持克制**：宁可少做、做精，不做成 framework；每加一个能力先过「不引入会具体坏在哪」(YAGNI) 闸门。
- **可移植的理念 > 绑定的实现**：核心资产是「分层 + 有界上下文 + compact/recall + 参考设计映射」，平台适配层应可替换。
