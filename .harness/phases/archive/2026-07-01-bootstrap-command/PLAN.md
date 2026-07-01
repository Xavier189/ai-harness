# Phase Plan: bootstrap-command

## Goal（有边界的目标）

新增 `harness bootstrap`：在已有代码仓库上一键触发"首次上下文初始化"——确保 init、开一个 `bootstrap-context` phase（PLAN 指令 agent 读代码库填 CONTEXT/DECISIONS/STATE）、检测构建文件作线索、Java 栈提示 java-spring profile。配套 `check` 加 nudge：CONTEXT 仍是模板占位 → warning 提示跑 bootstrap。CLI 只做确定性脚手架+触发，真实填充由 agent 完成。

## In Scope / 涉及文件与接口

- `ai_harness.py`
  - `detect_stack_hints(root)`：探测 pom.xml/build.gradle/package.json/pyproject.toml/go.mod 等构建文件（**仅列出，不解析内容**，保 core 语言无关）。
  - `bootstrap_plan(hints)`：onboarding 专用 PLAN 模板（指令填 CONTEXT/DECISIONS/STATE + 跨仓项目经验：每仓独立 harness + 对称契约文档）。
  - `bootstrap(args)`：没 init 则用 --profile/--agent 先 init；active phase 时拒绝（先收尾）；开 bootstrap-context phase；打印线索 + Java→java-spring 建议 + 下一步引导。
  - `check_context_filled(root)`：CONTEXT.md 含模板占位 → warning「跑 harness bootstrap」；接入 run_checks。常量 `CONTEXT_PLACEHOLDERS`。
  - argparse：`bootstrap` 子命令（--profile 默认 core、--agent 默认 codex,claude）。
- `tests/test_harness_cli.py`：新增用例。

## Out of Scope（明确不做）

- 解析 pom/package 内容自动填 CONTEXT（YAGNI，破坏语言无关；agent 干）。
- 自动切 profile（只提示）。
- bootstrap 覆盖已 active phase（改为拒绝）。

## Tasks

- [ ] detect_stack_hints + bootstrap_plan + bootstrap + argparse
- [ ] check_context_filled 接入 run_checks
- [ ] 测试：bootstrap 开 phase、未 init 自动 init、active phase 拒绝、Java 提示、check nudge 命中/填充后消失、防漂移
- [ ] 端到端验证
- [ ] compact 并 archive

## 端到端验证（End-to-End Verification）

    python3 -m unittest discover -s tests          # 期望 OK（>59）
    python3 ai_harness.py check                    # 本仓 CONTEXT 已填 → 不应报 nudge；0 error
    python3 evals/run.py                           # 5 场景全过

## Acceptance Criteria

- `harness bootstrap` 落地并有测试；check nudge 生效。
- 不影响未用 bootstrap 的现有行为（零回归）。
- 本 phase 有清晰 handoff；`check` 0 error。
