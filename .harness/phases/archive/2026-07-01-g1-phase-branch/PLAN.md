# Phase Plan: g1-phase-branch

## Goal（有边界的目标）

G1 选项 1：`phase start --branch` opt-in 时创建/切换到 `phase/<slug>` 分支；archive 若发现你仍在 phase 分支则**提示一句**（不自动切回/不 merge/不 commit）。subprocess 调 git，零依赖、fail-soft（git 缺失/非 repo 只 warning，phase 照常）。

## In Scope / 涉及文件与接口

- `ai_harness.py`
  - `import subprocess`；常量 `PHASE_BRANCH_PREFIX = "phase/"`
  - git helpers（全 fail-soft、零依赖）：`git_available()`、`in_git_repo(root)`、`current_git_branch(root)`、`branch_exists(root,name)`、`ensure_phase_branch(root,slug) -> (ok,msg)`
  - `phase_start`：新增 `--branch` 时，**先**切/建分支（打印 git: <msg>），**再**写 phase 文件（脚手架落在新分支）；git 步失败只 warning，文件照写
  - `phase_archive`：结束后若 `current_git_branch` 以 `phase/` 开头 → 打印提示「你仍在 phase 分支 X，记得 merge 回主干或切回」
  - argparse：`start.add_argument("--branch", action="store_true")`
- `tests/test_harness_cli.py`：新增用例。

## Out of Scope（明确不做）

- archive 自动切回主干 / auto-merge / auto-commit（ADR-0001 风险项）。
- worktree、持久 config 开关（`git.autoBranch`）、`check` 感知 branch↔phase 一致性。
- checkpoint/compact 碰 git。

## Tasks

- [ ] git helpers（subprocess，fail-soft）
- [ ] `phase start --branch`（先切分支再写文件）
- [ ] `phase archive` phase 分支提示
- [ ] argparse --branch
- [ ] 测试：非 repo fail-soft、创建分支、已存在切换、archive 提示、不带 --branch 零行为变化
- [ ] 端到端验证（含在临时 git repo 手验）
- [ ] compact 并 archive

## 端到端验证（End-to-End Verification）

    python3 -m unittest discover -s tests          # 期望 OK（>54）
    python3 ai_harness.py check                    # 0 error
    python3 evals/run.py                           # 5 场景全过
    # 手验：临时 git repo → phase start demo --branch → 应在 phase/demo 分支；archive → 打印提示

## Acceptance Criteria

- `--branch` 落地、fail-soft 不崩、archive 提示到位；有针对性测试。
- 不带 `--branch` 时行为与现在完全一致（零回归）。
- 本 phase 有清晰 handoff；`check` 0 error。
