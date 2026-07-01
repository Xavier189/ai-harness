# Phase Plan: workflow-task-next

## Goal（有边界的目标）

落地"最小三件"让工作流从隐式变显式：SKILL.md 编码完整循环、`harness task "<目标>"` 捕获意图开 phase、`harness next` 状态感知叙述下一步。全跨工具（CLI stdout + skill）、零依赖、opt-in。

## In Scope / 涉及文件与接口

- `ai_harness.py`
  - `current_plan(slug, goal="")`：goal 非空时预填进 Goal 段。
  - `task(args)`：捕获目标 → 派生/指定 slug（纯中文兜底 task）→ 开 phase（Goal 预填、可 --branch、active 时拒绝）。
  - `next_step(args)`：读 state.yml + CONTEXT 是否模板 → 打印状态化下一步（idle+空→bootstrap；idle+已填→task；active→checkpoint；compact→archive）。
  - `skill_doc()`：改写为"完整工作流"（init→bootstrap→task→checkpoint→compact→archive + next/recall/check）。
  - argparse：`task <goal> [--slug] [--branch]`、`next`。
- `.agents/skills/ai-harness/SKILL.md`：按新 skill_doc() 重生成（本仓 dogfood）。
- `tests/`：task 派生/中文兜底/active 拒绝、next 状态分支、skill 完整循环。

## Out of Scope（明确不做）

- spec-kit 式多命令流水线（constitution/specify/clarify/... ceremony，HD-0005 否决）。
- 把 slash 命令做成主驱动（破跨工具；--with-commands 保留为可选糖）。
- 带依赖的 workflow 引擎 / 交互式 wizard（破零依赖）。

## Tasks

- [ ] current_plan goal 注入 + task + next_step + skill_doc + argparse
- [ ] 重生成本仓 SKILL.md
- [ ] 测试 + 端到端验证
- [ ] compact 并 archive

## 端到端验证（End-to-End Verification）

    python3 -m unittest discover -s tests          # 期望 OK（>67）
    python3 ai_harness.py next                      # 打印状态化下一步
    python3 ai_harness.py check                     # 0 error
    python3 evals/run.py                            # 5 场景全过

## Acceptance Criteria

- task/next 落地、skill 编码完整循环、有测试；跨工具零依赖 opt-in。
- 不影响未用新命令的现有行为（零回归）。
- `check` 0 error；本 phase 有清晰 handoff。
