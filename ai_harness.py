#!/usr/bin/env python3
"""AI Harness.

单文件 CLI，用于初始化和维护轻量 AI harness：
人读规则放在 docs/，机器状态和 phase 状态放在 .harness/。
版本见 `__version__`（pyproject 与 --version 的单一来源）。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = 2
__version__ = "0.10.0"  # pyproject 与 --version 的单一来源（N4）
PHASE_STATES = (
    "idle",
    "discover",
    "discuss",
    "design",
    "plan",
    "execute",
    "verify",
    "compact",
    "archive",
)
CURRENT_FILES = ("PLAN.md", "PROGRESS.yml", "EVIDENCE.md", "HANDOFF.md")

# G5：活动态 phase（开着但未收尾）；idle 不查 stale，compact 已有专门提示，archive 是瞬态。
ACTIVE_PHASE_STATES = ("discover", "discuss", "design", "plan", "execute", "verify")

# G1：opt-in `phase start --branch` 用的分支前缀。
PHASE_BRANCH_PREFIX = "phase/"

# bootstrap：探测这些构建文件作为"技术栈线索"（仅列出、不解析内容，保 core 语言无关）。
BUILD_FILE_HINTS = (
    "pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle",
    "package.json", "pyproject.toml", "requirements.txt", "go.mod",
    "Cargo.toml", "Gemfile", "composer.json",
)
# bootstrap check nudge：CONTEXT 仍含这些模板占位串 → 提示未 onboarding。与 context_doc() 同源。
CONTEXT_PLACEHOLDERS = ("在这里补充人读项目目标", "在这里补充稳定 subsystem")

# Skill 唯一真实来源放 .agents/，Claude 侧用软链指回，避免多份事实来源。
SKILL_CANONICAL_DIR = ".agents/skills/ai-harness"
SKILL_LINK_DIR = ".claude/skills/ai-harness"
LEGACY_CURSOR_SKILL_DIR = ".cursor/skills/ai-harness"  # v0.8 遗留副本，Cursor 已原生扫 .agents/

# 既有库旧命名 -> 新结构的安全 rename 映射（仅当目标不存在才移动）。
MIGRATIONS = (
    ("docs/ai-harness/current-status.md", "docs/ai-harness/STATE.md"),
    ("docs/ai-harness/decision-log.md", "docs/ai-harness/DECISIONS.md"),
    ("docs/ai-harness/artifact-index.md", "docs/ai-harness/INDEX.md"),
    (".harness/memory.md", ".harness/memory/lessons.md"),
)
# 语义需人工并入、不自动 move 的旧文件 -> 去向提示。
MIGRATION_ADVISORIES = (
    ("docs/ai-harness/engineering-guidelines.md", "docs/ai-harness/POLICIES.md 的「工程基线」章节"),
    ("docs/ai-harness/implementation-plan.md", "项目级 roadmap / numbered phases"),
    ("docs/ai-harness/task-board.md", "项目级 backlog"),
)


@dataclass(frozen=True)
class Issue:
    level: str
    path: str
    message: str


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def write_text(path: Path, content: str, dry_run: bool = False) -> bool:
    current = read_text(path)
    if current == content:
        return False
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return True


def append_text(path: Path, content: str, dry_run: bool = False) -> bool:
    current = read_text(path)
    new_content = current.rstrip() + "\n\n" + content.strip() + "\n"
    return write_text(path, new_content, dry_run=dry_run)


def ensure_dir(path: Path, dry_run: bool = False) -> None:
    if not dry_run:
        path.mkdir(parents=True, exist_ok=True)


def ensure_symlink(link: Path, target: Path, dry_run: bool = False) -> bool:
    """让 link 成为指向 target 的相对软链；软链不可用时回退为复制目标内容。

    返回 True 表示发生了变更。相对路径保证 clone/移动后仍有效。
    回退（如未开开发者模式的 Windows）后 link 变成普通副本，由 `check` 提示退化。
    """
    rel_target = os.path.relpath(target, link.parent)
    if link.is_symlink():
        try:
            if os.readlink(link) == rel_target:
                return False
        except OSError:
            pass
    if dry_run:
        return True
    # 清掉遗留的普通文件/目录/错误软链，再重建
    if link.is_symlink() or link.exists():
        if link.is_dir() and not link.is_symlink():
            shutil.rmtree(link)
        else:
            link.unlink()
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.symlink(rel_target, link, target_is_directory=target.is_dir())
    except (OSError, NotImplementedError):
        # 软链不可用 -> 回退为普通副本（check 会提示需手动同步）
        if target.is_dir():
            shutil.copytree(target, link)
        else:
            shutil.copy2(target, link)
    return True


def managed_block(name: str, body: str) -> str:
    return (
        f"<!-- AI-HARNESS:{name}:START -->\n"
        f"{body.strip()}\n"
        f"<!-- AI-HARNESS:{name}:END -->"
    )


def upsert_managed_block(path: Path, name: str, body: str, dry_run: bool = False) -> bool:
    block = managed_block(name, body)
    current = read_text(path)
    start = f"<!-- AI-HARNESS:{name}:START -->"
    end = f"<!-- AI-HARNESS:{name}:END -->"
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
    if pattern.search(current):
        new_content = pattern.sub(block, current)
    elif current.strip():
        new_content = current.rstrip() + "\n\n" + block + "\n"
    else:
        new_content = block + "\n"
    return write_text(path, new_content, dry_run=dry_run)


def project_name(root: Path, override: str | None) -> str:
    return override or root.resolve().name


def state_yaml(name: str, profile: str, status: str = "idle", slug: str = "") -> str:
    started_at = utc_now() if status != "idle" else ""
    return f"""schemaVersion: {SCHEMA_VERSION}
project:
  name: "{name}"
  profile: "{profile}"
phase:
  status: {status}
  slug: "{slug}"
  startedAt: "{started_at}"
  currentPath: ".harness/phases/current"
context:
  requiredRead:
    - docs/ai-harness/STATE.md
    - docs/ai-harness/CONTEXT.md
    - docs/ai-harness/DECISIONS.md
  optionalRead:
    - .harness/phases/current/PLAN.md
limits:
  agentsMaxLines: 180
  stateMaxLines: 150
  planMaxLines: 300
  lessonsMaxLines: 200
"""


def parse_state(path: Path) -> dict[str, str]:
    text = read_text(path)
    result = {
        "schemaVersion": "",
        "project.name": "",
        "project.profile": "",
        "phase.status": "idle",
        "phase.slug": "",
        "phase.startedAt": "",
    }
    section = ""
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" ") and line.endswith(":"):
            section = line[:-1]
            continue
        if not line.startswith(" ") and ":" in line:
            key, value = line.split(":", 1)
            result[key.strip()] = clean_scalar(value)
            continue
        if section and line.startswith("  ") and ":" in line:
            key, value = line.strip().split(":", 1)
            result[f"{section}.{key.strip()}"] = clean_scalar(value)
    return result


def clean_scalar(value: str) -> str:
    value = value.strip()
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    return value


def replace_state_fields(text: str, fields: dict[str, str]) -> str:
    """定点替换 state.yml/config.yml 中给定字段，其余行原样保留（N1 方案 A）。

    fields 的键用 parse_state 的点号形式（顶层 scalar 如 "schemaVersion"，
    嵌套如 "phase.status"）。只改命中行——用户对 limits/context/requiredRead
    的定制全部保真，避免 update_state 全量重渲染造成的静默丢失。
    """

    def fmt(dotted: str, value: str) -> str:
        # status 与 schemaVersion 是裸标量；其余沿用模板的双引号风格
        if dotted in ("phase.status", "schemaVersion"):
            return str(value)
        return f'"{value}"'

    out: list[str] = []
    section = ""
    for raw_line in text.splitlines():
        line = raw_line
        stripped = line.strip()
        # 顶层 section 头（无缩进、以 : 结尾）
        if line and not line.startswith(" ") and stripped.endswith(":"):
            section = stripped[:-1]
            out.append(line)
            continue
        # 顶层 scalar（无缩进、含 :）
        if line and not line.startswith(" ") and ":" in stripped:
            key = stripped.split(":", 1)[0].strip()
            if key in fields:
                out.append(f"{key}: {fmt(key, fields[key])}")
                continue
            out.append(line)
            continue
        # 嵌套 "  key: value"
        if line.startswith("  ") and section and ":" in stripped and not stripped.endswith(":"):
            key = stripped.split(":", 1)[0].strip()
            dotted = f"{section}.{key}"
            if dotted in fields:
                indent = line[: len(line) - len(line.lstrip())]
                out.append(f"{indent}{key}: {fmt(dotted, fields[dotted])}")
                continue
        out.append(line)
    result = "\n".join(out)
    if text.endswith("\n"):
        result += "\n"
    return result


def update_state(root: Path, **updates: str) -> bool:
    state_path = root / ".harness/state.yml"
    if not state_path.exists():
        # 尚未初始化（正常路径不会到这里）：按模板生成
        name = updates.get("project.name", root.name)
        profile = updates.get("project.profile", "core")
        status = updates.get("phase.status", "idle")
        slug = updates.get("phase.slug", "")
        return write_text(state_path, state_yaml(name, profile, status, slug))
    current = parse_state(state_path)
    fields: dict[str, str] = {}
    for key in ("project.name", "project.profile", "phase.slug"):
        if key in updates:
            fields[key] = updates[key]
    if "phase.status" in updates:
        status = updates["phase.status"]
        fields["phase.status"] = status
        old_status = current.get("phase.status") or "idle"
        if status == "idle":
            fields["phase.startedAt"] = ""            # 收尾清零
        elif old_status == "idle":
            fields["phase.startedAt"] = utc_now()     # 只在进入新 phase 时打时间戳
        # 其余（非 idle→非 idle，如 checkpoint）保留原 startedAt 不动
    return write_text(state_path, replace_state_fields(read_text(state_path), fields))


def core_readme() -> str:
    return """# AI Harness

这个目录存放人读 AI 协作说明。机器 state、phase 进度、archive 和 check
输出放在 `.harness/`。

## 文件

| 文件 | 用途 |
|---|---|
| `STATE.md` | 当前短状态，必须保持有界。 |
| `CONTEXT.md` | 稳定项目地图、领域语言、架构边界。 |
| `DECISIONS.md` | 仍然有效的 decision 索引。 |
| `INDEX.md` | 重要人读 artifact 索引。 |
| `POLICIES.md` | 工程与协作 policy。 |

## 规则

- 启动上下文必须短。
- archive 只通过 `harness recall` 或明确需要历史上下文时读取。
- `.harness/state.yml` 是 phase status 的机器 source of truth。
- 完成的 phase 必须先 compact，再进入下一 phase。
"""


def state_doc(name: str) -> str:
    return f"""# 当前状态

项目：`{name}`

## Phase

- Status: `idle`
- Current phase: 无
- Next action: 开始有边界的工作时运行 `harness phase start <slug>`。

## 当前焦点

- harness 已初始化。
- 当前没有 active implementation phase。
- 跨版本进度记 `ROADMAP.md`；本文只保当前状态（`phase archive` 会重置本文）。

## 阻塞

- 暂无。

## 验证

- 修改 harness 文件后运行 `harness check`。
"""


def context_doc(name: str) -> str:
    return f"""# 项目上下文

## 项目

- Name: `{name}`
- 用途：在这里补充人读项目目标。

## 架构地图

- 在这里补充稳定 subsystem 边界。
- 在这里补充 domain vocabulary。
- 临时 phase 工作放在 `.harness/phases/current/`，不要写进本文。

## Context Loading

- 重要工作开始前读取本文。
- 不要把 session transcript 或 implementation log 追加到本文。
"""


def decisions_doc() -> str:
    return """# 有效决策

本文只索引仍然约束项目的 decision。

| ID | Decision | Source |
|---|---|---|
| HD-0001 | 人读 policy 放在 `docs/`；机器和 phase state 放在 `.harness/`。 | Harness initialization |

历史 decision 或已被取代的 decision 应进入 phase archive 或 ADR，不放在本索引。
"""


def index_doc(profile: str) -> str:
    profile_line = "- `docs/ai-harness/POLICIES.md` - 工程 policy"
    if profile == "java-spring":
        profile_line += "，包含 Java/Spring profile"
    return f"""# Harness 索引

## 启动文档

- `docs/ai-harness/STATE.md` - 当前短状态
- `docs/ai-harness/CONTEXT.md` - 稳定项目地图
- `docs/ai-harness/DECISIONS.md` - 有效 decision 索引
- `docs/ai-harness/ROADMAP.md` - 项目级 numbered phases + backlog
- `.harness/phases/current/PLAN.md` - 当前 phase plan，仅 active phase 时读取

## Policy 文档

{profile_line}
- `docs/ai-harness/OUT-OF-SCOPE.md` - 项目级「明确不做」清单（与 PLAN 的 phase 级 out-of-scope 分层）

## 决策记录

- `docs/adr/0000-template.md` - ADR 模板（复制为 `NNNN-<slug>.md` 新建）

## 机器状态

- `.harness/state.yml` - phase state source of truth
- `.harness/checks/latest.json` - 最新 harness check 输出

## Archives

- `.harness/phases/archive/` - phase history，通过 `harness recall` 检索
"""


def policies_doc(profile: str) -> str:
    base = """# Harness Policies

## Core Harness Policy

- `docs/` 用于人读 standard、policy、decision 和 design doc。
- `.harness/` 用于机器可读 state、active phase progress、archive 和生成的 check 输出。
- 启动文件只负责把 agent 路由到有界 context；它们不是 knowledge base。
- archive folder 默认不读取。
- `STATE.md` 是有界的"当前状态"：只写当前 phase / 焦点 / 阻塞；跨版本进度记 `ROADMAP.md`（`phase archive` 会重置 STATE，别在此累积历史）。
- spec 和 policy 不写 copy/install/research note，除非文件明确是 usage guide。

## 工程基线（Engineering Baseline）

适用于任何技术栈的设计与实现底线；按需在 design/verify phase 读取，不必每次启动加载。

- **方案评判四原则**：业务可落地 > 稳定性 > 性能 > 可演进，逐项过一遍，不允许只讲功能实现。
- **Trade-off 显式化**：两个以上可行方案必须给对比 + 推荐 + 理由；单方案直推视为评审不通过。
- **YAGNI**：只写当前需要的代码；为"将来可能"预留的抽象必须能指出 6 个月内的真实触发场景，否则删掉。
- **失败路径优先**：先设计超时、重试、降级、fail-closed，再写正常路径；测试同理。
- **多视角推演**：涉及外部交互、数据、安全的设计，至少补"运维半夜排查"与"安全合规"两个视角。
- **最新稳定惯用法**：用语言/框架当前推荐写法，不写已被取代的旧 API；但引入新框架/新架构是高风险动作，先过成熟度 + 可回退 + 团队可维护性闸门，核心链路偏稳健。
- **异常归宿点**：堆栈只在归宿点打一次完整日志，中间层只补一行摘要，不泄露 secret 或完整 payload。

## 协作模式（Subagent / Context）

- 调研或大范围读代码用 subagent fan-out，每个子代理只回 1–2k 蒸馏摘要，主上下文保持干净。
- 主 agent 维护高层 plan，子代理做深度技术工作；单任务尽量在干净上下文里完成。
- verify 用 fresh-context 子代理做对抗式复查：先查 spec 合规、再查代码质量；只报影响正确性 / 需求的 gap，避免过度工程。
"""
    if profile == "java-spring":
        base += """

## Java/Spring Profile

- 目标项目使用 Spring 时，优先采用 Java 17+ 和 Spring Boot 3.x idiom。
- 保持 Controller、application、domain、infrastructure 职责分离。
- public API 使用稳定 response envelope 和明确 business error code。
- 日志必须能定位 operation、reason、traceId、dependency、latency，同时不能泄露 secret 或完整 payload。
- build/test command 属于项目专属 config 或 `STATE.md`，不要写进可复用 policy template。
"""
    return base


def current_plan(slug: str = "", goal: str = "") -> str:
    title = slug or "no-active-phase"
    goal_line = f"- {goal}" if goal else '- 用一句话写清楚"做完什么算完成"。'
    return f"""# Phase Plan: {title}

## Goal（有边界的目标）

{goal_line}

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
"""


def progress_yml(slug: str = "") -> str:
    return f"""phase: "{slug}"
status: idle
tasks: []
checkpoints: []
"""


def evidence_doc(slug: str = "") -> str:
    return f"""# Evidence: {slug or 'no-active-phase'}

在这里记录 verification command、重要输出和未解决风险。

## 验证

- 尚未运行。

## Verify Checklist（收尾前逐条过，不适用标 N/A）

- [ ] 失败路径已验证：超时 / 重试 / 降级 / fail-closed。
- [ ] 多视角已过：运维半夜排查、安全合规。
- [ ] 异常归宿点：堆栈只在归宿点打一次，不泄露 secret / 完整 payload。
- [ ] 对外契约变更已告知下游。
- [ ] 端到端验证有真实输出，非"看起来好了"。
"""


def handoff_doc(slug: str = "") -> str:
    return f"""# Handoff: {slug or 'no-active-phase'}

## 当前状态

- 尚未写入 handoff。

## Next Step

- compact 或 context reset 前更新本文。
"""


def agents_body(profile: str) -> str:
    profile_hint = (
        "- Java/Spring profile 已启用；进行 Java/Spring design 或 coding 前读取 `docs/ai-harness/POLICIES.md`。"
        if profile == "java-spring"
        else "- Core profile 已启用；项目专属技术 policy 可追加到 `docs/ai-harness/POLICIES.md`。"
    )
    return f"""## AI Harness

- 人读说明放在 `docs/ai-harness/`；机器和 phase state 放在 `.harness/`。
- 重要工作开始前读取 `docs/ai-harness/STATE.md`、`docs/ai-harness/CONTEXT.md`、`docs/ai-harness/DECISIONS.md`。
- 任务属于 active phase 时才读取 `.harness/phases/current/PLAN.md`。
- 默认不读 `.harness/phases/archive/**`；需要历史上下文时使用 `harness recall <keyword>`。
- 保持本入口文件短小；稳定 policy 放到 `docs/ai-harness/POLICIES.md`。
- Skill 唯一来源在 `.agents/skills/ai-harness/SKILL.md`（Codex / Cursor 原生扫描；Claude 经 `.claude/skills/ai-harness` 软链指回）。
{profile_hint}
"""


def skill_doc() -> str:
    return """---
name: ai-harness
description: 本仓库用 ai-harness 管理 AI 协作上下文与有边界的工作 phase。当需要了解当前任务状态、开始/推进/收尾一个 phase、检索历史决策或归档、或维护 docs/ai-harness 与 .harness 时使用本 skill。保留 CLI、phase、state.yml、AGENTS.md、CLAUDE.md 等技术名词原文。
---

# AI Harness（本仓库）

本仓库已安装 ai-harness：人读规范在 `docs/ai-harness/`，机器 state、当前 phase、archive、check 输出在 `.harness/`。

## 开工前先读

- `docs/ai-harness/STATE.md` — 当前短状态。
- `docs/ai-harness/CONTEXT.md` — 稳定项目地图、领域语言、架构边界。
- `docs/ai-harness/DECISIONS.md` — 仍然有效的 decision 索引。
- 仅当任务属于 active phase 时，再读 `.harness/phases/current/PLAN.md`。
- 默认不读 `.harness/phases/archive/**`；需要历史上下文时用 `harness recall <keyword>`。

## 完整工作流（不确定下一步就跑 `harness next`）

```bash
harness init                 # ① 已有代码仓库也安全：只加不覆盖、不碰源码
harness bootstrap            # ② 首次：开 bootstrap-context phase，读代码库填 CONTEXT/DECISIONS/STATE
harness task "<目标>" [--branch]   # ③ 每个任务：带目标开有界 phase（Goal 预填进 PLAN，--branch 顺带建 phase/<slug>）
harness phase checkpoint --status <state> --note "<note>"   # ④ 推进：记进度
harness phase compact        # ⑤ 收尾：压成高保真 handoff
harness phase archive        # ⑥ 归档回 idle，再开下一个
harness next                 # 任意时刻：告诉你现在该跑什么
harness recall <keyword>     # 从 archive/memory 检索历史
harness check                # 校验 harness 卫生（可挂 Stop hook）
```

合法 phase state：`idle, discover, discuss, design, plan, execute, verify, compact, archive`。
`harness phase start <slug>` 是 `task` 的底层等价物（不预填 goal）；日常优先用 `task`。

> CLI 入口：装好后用 `harness`（`uv tool install ai-harness` 或 `pipx install ai-harness`）；未装可 `uvx --from <repo> ai-harness`，或源码直跑 `python3 ai_harness.py`。

## 规则

- 启动上下文保持短小；稳定 policy 放 `docs/ai-harness/POLICIES.md`，不要堆进 AGENTS.md/CLAUDE.md。
- 完成的 phase 先 compact，再 archive，再开下一个。
- PLAN.md 当 self-contained spec 写：点名文件/接口、写明 out-of-scope、给端到端验证步骤。
- 调研用 subagent fan-out 只回蒸馏摘要；verify 用 fresh-context 对抗式复查（先 spec 合规、再代码质量）。
"""


# upgrade --refresh-infra 可安全覆盖的纯模板文件（用户极少手改）。
INFRA_FILES = (
    "docs/ai-harness/README.md",
    "docs/adr/0000-template.md",
    ".agents/skills/ai-harness/SKILL.md",
)


def harness_dirs(root: Path) -> list[Path]:
    return [
        root / "docs/ai-harness",
        root / "docs/design",
        root / "docs/adr",
        root / ".harness/phases/current",
        root / ".harness/phases/archive",
        root / ".harness/checks",
        root / ".harness/memory/topics",
        root / SKILL_CANONICAL_DIR,
    ]


def harness_files(root: Path, name: str, profile: str, agents: set[str]) -> dict[Path, str]:
    return {
        root / "docs/ai-harness/README.md": core_readme(),
        root / "docs/ai-harness/STATE.md": state_doc(name),
        root / "docs/ai-harness/CONTEXT.md": context_doc(name),
        root / "docs/ai-harness/DECISIONS.md": decisions_doc(),
        root / "docs/ai-harness/INDEX.md": index_doc(profile),
        root / "docs/ai-harness/POLICIES.md": policies_doc(profile),
        root / "docs/ai-harness/ROADMAP.md": roadmap_doc(),
        root / "docs/ai-harness/OUT-OF-SCOPE.md": out_of_scope_doc(),
        root / "docs/adr/0000-template.md": adr_template_doc(),
        root / ".harness/config.yml": config_yml(name, profile, agents),
        root / ".harness/state.yml": state_yaml(name, profile),
        root / ".harness/phases/current/PLAN.md": current_plan(),
        root / ".harness/phases/current/PROGRESS.yml": progress_yml(),
        root / ".harness/phases/current/EVIDENCE.md": evidence_doc(),
        root / ".harness/phases/current/HANDOFF.md": handoff_doc(),
        root / ".harness/memory/lessons.md": lessons_doc(),
        root / ".harness/checks/latest.json": initial_check_json(),
        root / ".harness/phases/archive/.gitkeep": archive_keep(),
        root / f"{SKILL_CANONICAL_DIR}/SKILL.md": skill_doc(),
    }


def init_harness(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    name = project_name(root, args.project_name)
    profile = args.profile
    agents = parse_agents(args.agent)
    dry = args.dry_run

    for directory in harness_dirs(root):
        ensure_dir(directory, dry_run=dry)

    changes = []

    for path, content in harness_files(root, name, profile, agents).items():
        if path.exists():
            continue
        if write_text(path, content, dry_run=dry):
            changes.append(str(path.relative_to(root)))

    if "codex" in agents:
        if upsert_managed_block(root / "AGENTS.md", "ROUTER", agents_body(profile), dry_run=dry):
            changes.append("AGENTS.md")
    if "claude" in agents:
        if upsert_managed_block(root / "CLAUDE.md", "ROUTER", agents_body(profile), dry_run=dry):
            changes.append("CLAUDE.md")
        if ensure_symlink(root / SKILL_LINK_DIR, root / SKILL_CANONICAL_DIR, dry_run=dry):
            changes.append(f"{SKILL_LINK_DIR} (symlink -> {SKILL_CANONICAL_DIR})")

    if args.with_hooks:
        if write_stop_hook(root, dry_run=dry):
            changes.append(".claude/settings.json")

    if args.with_commands:
        for rel in write_harness_commands(root, dry_run=dry):
            changes.append(rel)

    issues = run_checks(root)
    write_check_result(root, issues, dry_run=dry)

    prefix = "[dry-run] " if dry else ""
    if changes:
        print(prefix + "已初始化/更新：")
        for change in changes:
            print(f"  - {change}")
    else:
        print(prefix + "harness 已是最新")
    print_issue_summary(issues)
    return 1 if any(issue.level == "error" for issue in issues) else 0


def write_stop_hook(root: Path, dry_run: bool = False) -> bool:
    """幂等注入 Stop hook：agent 停止前跑 harness check。已有 settings.json 则合并保留原内容。"""
    path = root / ".claude/settings.json"
    existing = read_text(path)
    try:
        data = json.loads(existing) if existing.strip() else {}
    except json.JSONDecodeError:
        return False  # 不破坏无法解析的既有文件
    if not isinstance(data, dict):
        return False
    command = 'AI_HARNESS_BIN="${AI_HARNESS_BIN:-harness}"; "$AI_HARNESS_BIN" --root "$CLAUDE_PROJECT_DIR" check'
    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        return False
    stop = hooks.setdefault("Stop", [])
    if not isinstance(stop, list):
        return False
    for entry in stop:
        if not isinstance(entry, dict):
            continue
        for hook in entry.get("hooks", []):
            if isinstance(hook, dict) and "harness" in hook.get("command", "") and "check" in hook.get("command", ""):
                return False  # 已注入
    stop.append({"matcher": "", "hooks": [{"type": "command", "command": command}]})
    return write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n", dry_run=dry_run)


HARNESS_COMMANDS = {
    "harness-phase.md": """---
description: 引导一个 harness phase：start / checkpoint / compact / archive
---

你是在帮用户走 harness phase 生命周期。请按 CLI 顺序执行并解释每一步：

1. 若当前 `harness status` 不是 idle，先帮用户决定继续推进还是先 archive。
2. 用 `harness phase start <slug>` 开 phase（slug 用 kebab-case 概括目标）。
3. 工作过程中，关键节点用 `harness phase checkpoint --status <state> --note <一句话>`。
   合法 state: discover/discuss/design/plan/execute/verify/compact/archive。
4. 收尾前 `harness phase compact`，再 `harness phase archive`。
5. 每一步都把 CLI 输出贴回，让用户能看见 state 变化。

只做编排，不擅自修改 PLAN.md / EVIDENCE.md / HANDOFF.md 内的业务文字——那是 agent 与用户共同填写的。
""",
    "harness-recall.md": """---
description: 用 harness recall 在 archive/memory 检索关键词
---

调用 `harness recall <keyword>` 从 `.harness/phases/archive/` 与 `.harness/memory/` 检索关键词。
- 用户给了模糊问题先转成 1~3 个高质量 keyword 再分别 recall。
- 把命中行（路径 + 行号 + 原文）原样贴回，不要重写。
- 命中后判断是 lesson 还是过期细节：lesson 留 lessons.md，细节留 archive 即可。
""",
    "harness-check.md": """---
description: 跑 harness check 并解释问题
---

执行 `harness --root . check`，把 stdout 完整贴回。对每个 error/warning：
- 解释问题归因（链接断裂 / 行数超阈值 / 退化软链 / 分层错位）。
- 给出一条最小修复动作建议。
- 不擅自修复，除非用户确认。
""",
}


def write_harness_commands(root: Path, dry_run: bool = False) -> list[str]:
    """在 .claude/commands/ 幂等生成 harness-* slash command 模板。返回新增的相对路径。"""
    added: list[str] = []
    base = root / ".claude/commands"
    ensure_dir(base, dry_run=dry_run)
    for name, body in HARNESS_COMMANDS.items():
        target = base / name
        if write_text(target, body, dry_run=dry_run):
            added.append(str(target.relative_to(root)))
    return added


def parse_config_agents(root: Path) -> set[str]:
    text = read_text(root / ".harness/config.yml")
    agents: set[str] = set()
    in_agents = False
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("agents:"):
            in_agents = True
            continue
        if in_agents:
            stripped = line.strip()
            if stripped.startswith("- "):
                agents.add(stripped[2:].strip())
            elif line and not line.startswith(" "):
                break
    return agents or {"codex"}


def upgrade(args: argparse.Namespace) -> int:
    """把已初始化的库对齐到当前模板：补齐缺失文件、可选刷新纯模板文件、bump schemaVersion。"""
    root = Path(args.root).resolve()
    ensure_initialized(root)
    state = parse_state(root / ".harness/state.yml")
    from_version = state.get("schemaVersion") or "?"
    name = state.get("project.name") or root.name
    profile = state.get("project.profile") or "core"
    agents = parse_config_agents(root)
    dry = not args.apply

    added: list[str] = []
    refreshed: list[str] = []

    for directory in harness_dirs(root):
        ensure_dir(directory, dry_run=dry)

    for path, content in harness_files(root, name, profile, agents).items():
        rel = str(path.relative_to(root))
        if not path.exists():
            if write_text(path, content, dry_run=dry):
                added.append(rel)
        elif args.refresh_infra and rel in INFRA_FILES:
            if write_text(path, content, dry_run=dry):
                refreshed.append(rel)

    for entry_file in ("AGENTS.md", "CLAUDE.md"):
        entry_path = root / entry_file
        if entry_path.exists() and "AI-HARNESS:ROUTER:START" in read_text(entry_path):
            if upsert_managed_block(entry_path, "ROUTER", agents_body(profile), dry_run=dry):
                refreshed.append(entry_file)

    if "claude" in agents:
        if ensure_symlink(root / SKILL_LINK_DIR, root / SKILL_CANONICAL_DIR, dry_run=dry):
            refreshed.append(f"{SKILL_LINK_DIR} (symlink -> {SKILL_CANONICAL_DIR})")

    if args.with_hooks:
        if write_stop_hook(root, dry_run=dry):
            added.append(".claude/settings.json")

    if args.with_commands:
        for rel in write_harness_commands(root, dry_run=dry):
            added.append(rel)

    bumped = str(from_version) != str(SCHEMA_VERSION)
    if bumped and not dry:
        # 显式 bump state.yml 的 schemaVersion（定点替换，保真其余内容）；
        # 不再依赖 update_state 全量重渲染——否则普通 phase 操作会静默刷版本，N2 就测不到 mismatch。
        state_path = root / ".harness/state.yml"
        write_text(state_path, replace_state_fields(read_text(state_path), {"schemaVersion": str(SCHEMA_VERSION)}))
        write_text(root / ".harness/config.yml", config_yml(name, profile, agents))

    prefix = "" if args.apply else "[dry-run] "
    print(f"{prefix}upgrade: schemaVersion {from_version} -> {SCHEMA_VERSION}")
    if added:
        print("新增：")
        for item in added:
            print(f"  - {item}")
    if refreshed:
        print("刷新：")
        for item in refreshed:
            print(f"  - {item}")
    if not added and not refreshed and not bumped:
        print("harness 已是最新")
    if not args.apply:
        print("预览模式：加 --apply 执行（--refresh-infra 刷新纯模板文件，--with-hooks 注入 Stop hook）。")
    return 0


def config_yml(name: str, profile: str, agents: set[str]) -> str:
    agent_list = "\n".join(f"  - {agent}" for agent in sorted(agents))
    return f"""schemaVersion: {SCHEMA_VERSION}
project:
  name: "{name}"
  profile: "{profile}"
agents:
{agent_list}
paths:
  docs: docs/ai-harness
  machine: .harness
  currentPhase: .harness/phases/current
  archive: .harness/phases/archive
"""


def lessons_doc() -> str:
    return """# Harness Lessons

只保留长期有效的 lesson；一次性过程细节留在 `.harness/phases/archive/`，
不要堆到这里（防止 memory 变成无界启动文档）。

## 晋升 / 淘汰约定

- 长期不变的工程偏好/红线 → 晋升到 `docs/ai-harness/POLICIES.md`。
- 一次性 phase 过程细节 → 在 archive 那条记录里就够，不进 lessons。
- 行数超过 `limits.lessonsMaxLines`（默认 200，可在 state.yml 调）时 `harness check`
  会 warning，按上面规则裁剪。

## 写入格式（每条一个带日期的小节）

```text
## YYYY-MM-DD（一句话主题）

### 完成了什么
- ...

### 已确认决策
- ...

### 阻塞 / 未解决
- ...

### 下一步
- ...
```
"""


def out_of_scope_doc() -> str:
    return """# Out of Scope（项目级）

项目级稳定的「明确不做」清单。与 `.harness/phases/current/PLAN.md` 的 phase 级 out-of-scope 分层：
项目级在这里，phase 级临时在 PLAN 里。

> 写入要求：**理由 + 触发重审条件**。没有重审条件的项不要写，否则会变成永久禁令。

## 不做的事

- _示例_：不做 GUI / web 控制台。**理由**：核心是单文件 CLI + 文本约定。
  **重审条件**：若每周新加入用户 ≥ 5 人且 70% 反馈来自非命令行用户。

## 与其它文档的边界

- `DECISIONS.md`：记「决定怎么做」。
- `OUT-OF-SCOPE.md`：记「明确不做」+ 重审触发条件。
- `PLAN.md` 的 Out of Scope：仅对当前 phase 临时有效，结束即过期。
"""


def roadmap_doc() -> str:
    return """# Roadmap

项目级规划：numbered phases + backlog。单个 active phase 的细节在
`.harness/phases/current/PLAN.md`，不要写进本文。

## Phases

| # | Phase | 目标（一句话） | 状态 |
|---|---|---|---|
| 1 | <slug> | <目标> | planned |

合法状态：`planned, active, done, dropped`。开工时用 `harness phase start <slug>`。

## Backlog（未排期）

- 待办项放这里；排期后提升为带编号的 phase。

## 已归档 Phase

- 见 `.harness/phases/archive/`，用 `harness recall <keyword>` 检索。
"""


def adr_template_doc() -> str:
    return """# ADR-0000：<标题>

> 复制本文件为 `NNNN-<slug>.md` 新建 ADR；本模板文件保留不动。

## 状态

提议 / 已接受 / 已取代（被 ADR-XXXX 取代）。

## 背景

- 什么问题或约束触发了这个决策。

## 决策

- 决定做什么。

## 结果

- 正面 / 负面后果，引入的新风险。

## 约束

- 这个决策施加的硬约束（后续不可随意推翻）。
"""


def initial_check_json() -> str:
    return json.dumps(
        {
            "generatedAt": utc_now(),
            "summary": {"errors": 0, "warnings": 0},
            "issues": [],
        },
        ensure_ascii=False,
        indent=2,
    ) + "\n"


def archive_keep() -> str:
    # 占位：让空的 archive 目录能被 git 跟踪（git 不跟踪空目录），fresh clone / CI checkout 才有此目录。
    # phase archive 后这里会出现 <日期>-<slug>/ 归档子目录。
    return "# 占位文件，勿删：保持空 archive 目录可被版本控制。\n"


def parse_agents(value: str) -> set[str]:
    agents = {item.strip().lower() for item in value.split(",") if item.strip()}
    unknown = agents - {"codex", "claude"}
    if unknown:
        raise SystemExit(f"unsupported agent(s): {', '.join(sorted(unknown))}")
    return agents or {"codex"}


def doctor(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    print(f"root: {root}")
    print(f"git: {'yes' if (root / '.git').exists() else 'no'}")
    print(f"harness: {'yes' if (root / '.harness/state.yml').exists() else 'no'}")
    for path in ("AGENTS.md", "CLAUDE.md", "docs/ai-harness/STATE.md"):
        status = "exists" if (root / path).exists() else "missing"
        print(f"{path}: {status}")
    return 0


def status(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    state_path = root / ".harness/state.yml"
    if not state_path.exists():
        print("harness 尚未初始化")
        return 1
    state = parse_state(state_path)
    print(f"project: {state.get('project.name', '')}")
    print(f"profile: {state.get('project.profile', '')}")
    print(f"phase: {state.get('phase.status', 'idle')}")
    print(f"slug: {state.get('phase.slug', '')}")
    print()
    state_md = root / "docs/ai-harness/STATE.md"
    if state_md.exists():
        print(first_lines(state_md, 40))
    return 0


def git_available() -> bool:
    return shutil.which("git") is not None


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(root), capture_output=True, text=True)


def in_git_repo(root: Path) -> bool:
    if not git_available():
        return False
    result = _git(root, "rev-parse", "--is-inside-work-tree")
    return result.returncode == 0 and result.stdout.strip() == "true"


def current_git_branch(root: Path) -> str | None:
    if not in_git_repo(root):
        return None
    result = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    return result.stdout.strip() if result.returncode == 0 else None


def ensure_phase_branch(root: Path, slug: str) -> tuple[bool, str]:
    """G1：创建/切换到 phase/<slug> 分支。返回 (ok, message)，全程 fail-soft。"""
    branch = f"{PHASE_BRANCH_PREFIX}{slug}"
    if not git_available():
        return False, "git 未安装，跳过分支创建"
    if not in_git_repo(root):
        return False, "非 git 仓库，跳过分支创建"
    if current_git_branch(root) == branch:
        return True, f"已在分支 {branch}"
    exists = _git(root, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}").returncode == 0
    if exists:
        result, action = _git(root, "checkout", branch), "切换到"
    else:
        result, action = _git(root, "checkout", "-b", branch), "创建并切换到"
    if result.returncode != 0:
        return False, f"git checkout 失败：{result.stderr.strip()}"
    return True, f"已{action}分支 {branch}"


def detect_stack_hints(root: Path) -> list[str]:
    """列出仓库根的构建文件作为技术栈线索（不解析内容，保 core 语言无关）。"""
    return [name for name in BUILD_FILE_HINTS if (root / name).exists()]


def bootstrap_plan(hints: list[str]) -> str:
    hint_line = "、".join(hints) if hints else "（未检测到常见构建文件）"
    return f"""# Phase Plan: bootstrap-context

## Goal（有边界的目标）

首次 onboarding：读本仓代码库，把 `docs/ai-harness/` 的 CONTEXT/DECISIONS/STATE 从模板填成真实内容，让后续 session 能带记忆冷启动。

## In Scope / 涉及文件与接口

- `docs/ai-harness/CONTEXT.md`：项目定位（一句话）、架构地图（子系统/模块职责与依赖）、domain vocabulary、关键设计约束。
- `docs/ai-harness/DECISIONS.md`：从代码/配置/README 读出的仍生效关键决策（每条一句话 + 出处）。
- `docs/ai-harness/STATE.md`：当前焦点、下一步。

检测到的技术栈线索（仅参考）：{hint_line}

## Out of Scope（明确不做）

- 不改任何业务源码；只填 harness 人读层。
- 不把大段源码/transcript 贴进 docs。

## Tasks

- [ ] 读 README / 构建文件 / 关键源码，蒸馏项目定位与架构。
- [ ] 填 CONTEXT.md（含 domain vocabulary 与约束）。
- [ ] 填 DECISIONS.md（关键决策 + 出处）。
- [ ] 更新 STATE.md 当前焦点。
- [ ] **若存在关联的兄弟仓库**：每仓保持独立 harness，把跨仓契约（接口/消息/共享 schema）**对称写进两边 CONTEXT 并互相 `../` 指向**——不要在父目录建总 harness。
- [ ] `harness check` 0 error（CONTEXT nudge 消失即为填充完成信号）。

## 端到端验证（End-to-End Verification）

- `harness check` 不再报「CONTEXT 仍是模板占位」；人读一遍 CONTEXT 能回答"这项目是什么/架构/关键决策"。

## Acceptance Criteria

- CONTEXT/DECISIONS/STATE 均为真实内容，非模板。
- `harness check` 0 error、无 context nudge。
"""


def bootstrap(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    if not (root / ".harness/state.yml").exists():
        # 没 init 则先 init（用 bootstrap 传入/默认的 profile+agent）
        init_harness(argparse.Namespace(
            root=str(root), profile=args.profile, agent=args.agent, project_name=None,
            with_hooks=False, with_commands=False, dry_run=False,
        ))
    ensure_initialized(root)
    state = parse_state(root / ".harness/state.yml")
    if (state.get("phase.status") or "idle") != "idle":
        raise SystemExit(
            f"已有 active phase `{state.get('phase.slug')}`；先 `harness phase compact` + `archive` 再 bootstrap"
        )

    hints = detect_stack_hints(root)
    slug = "bootstrap-context"
    current = root / ".harness/phases/current"
    ensure_dir(current)
    write_text(current / "PLAN.md", bootstrap_plan(hints))
    write_text(current / "PROGRESS.yml", progress_yml(slug).replace("status: idle", "status: discover"))
    write_text(current / "EVIDENCE.md", evidence_doc(slug))
    write_text(current / "HANDOFF.md", handoff_doc(slug))
    update_state(root, **{"phase.status": "discover", "phase.slug": slug})
    append_text(root / "docs/ai-harness/STATE.md", f"## Active Phase\n\n- Slug: `{slug}`\n- Status: `discover`\n- Started: `{utc_now()}`")

    print("已启动 bootstrap-context phase：让 AI agent 按 PLAN.md 读代码库、填 docs/ai-harness/。")
    if hints:
        print(f"  技术栈线索（未解析）：{'、'.join(hints)}")
    profile = state.get("project.profile") or "core"
    if profile == "core" and any(h == "pom.xml" or h.startswith("build.gradle") for h in hints):
        print("  建议：检测到 Java 栈，可用 java-spring profile（重跑 `harness init --profile java-spring` 补工程 policy）。")
    print("  下一步：让 agent 填 CONTEXT.md / DECISIONS.md / STATE.md，完成后 `harness check` 应无 context 提示。")
    return 0


def phase_start(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    ensure_initialized(root)
    slug = slugify(args.slug)
    if getattr(args, "branch", False):
        # 先切/建分支，让 phase 脚手架落在新分支上；git 失败只 warning，不阻断 phase。
        ok, msg = ensure_phase_branch(root, slug)
        print(f"{'  git: ' if ok else '  [warning] git: '}{msg}")
    current = root / ".harness/phases/current"
    ensure_dir(current)
    write_text(current / "PLAN.md", current_plan(slug))
    write_text(current / "PROGRESS.yml", progress_yml(slug).replace("status: idle", "status: discover"))
    write_text(current / "EVIDENCE.md", evidence_doc(slug))
    write_text(current / "HANDOFF.md", handoff_doc(slug))
    update_state(root, **{"phase.status": "discover", "phase.slug": slug})
    append_text(root / "docs/ai-harness/STATE.md", f"## Active Phase\n\n- Slug: `{slug}`\n- Status: `discover`\n- Started: `{utc_now()}`")
    print(f"已启动 phase：{slug}")
    return 0


def task(args: argparse.Namespace) -> int:
    """带目标开一个有界 phase：捕获意图、把 Goal 预填进 PLAN（bootstrap 之后的常规入口）。"""
    root = Path(args.root).resolve()
    ensure_initialized(root)
    state = parse_state(root / ".harness/state.yml")
    if (state.get("phase.status") or "idle") != "idle":
        raise SystemExit(f"已有 active phase `{state.get('phase.slug')}`；先 `harness phase compact` + `archive` 再开新任务")
    goal = args.goal.strip()
    if not goal:
        raise SystemExit("任务目标不能为空")
    fallback = False
    if args.slug:
        slug = slugify(args.slug)
    else:
        slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", goal).strip("-").lower()[:48].strip("-")
        if not slug:  # 纯中文等无 ASCII → 兜底
            slug, fallback = "task", True
    if getattr(args, "branch", False):
        ok, msg = ensure_phase_branch(root, slug)
        print(f"{'  git: ' if ok else '  [warning] git: '}{msg}")
    current = root / ".harness/phases/current"
    ensure_dir(current)
    write_text(current / "PLAN.md", current_plan(slug, goal))
    write_text(current / "PROGRESS.yml", progress_yml(slug).replace("status: idle", "status: discover"))
    write_text(current / "EVIDENCE.md", evidence_doc(slug))
    write_text(current / "HANDOFF.md", handoff_doc(slug))
    update_state(root, **{"phase.status": "discover", "phase.slug": slug})
    append_text(root / "docs/ai-harness/STATE.md",
                f"## Active Phase\n\n- Slug: `{slug}`\n- Status: `discover`\n- Goal: {goal}\n- Started: `{utc_now()}`")
    print(f"已开始任务 phase：{slug}")
    print(f"  目标：{goal}")
    if fallback:
        print("  提示：目标无 ASCII 字符，slug 用了 'task'；可加 --slug <名字> 指定更清晰的名。")
    print("  下一步：把 PLAN.md 写成 spec（In Scope / Out of Scope / 端到端验证），推进后 `harness phase checkpoint`。")
    return 0


def next_step(args: argparse.Namespace) -> int:
    """状态感知的"下一步"叙述器：读 state.yml，告诉你（和 agent）现在该跑什么。"""
    root = Path(args.root).resolve()
    if not (root / ".harness/state.yml").exists():
        print("harness 未初始化 → 运行 `harness init`（已有代码仓库也安全：只加不覆盖）")
        return 0
    state = parse_state(root / ".harness/state.yml")
    status = state.get("phase.status") or "idle"
    slug = state.get("phase.slug") or ""
    ctx = root / "docs/ai-harness/CONTEXT.md"
    ctx_is_template = ctx.exists() and any(p in read_text(ctx) for p in CONTEXT_PLACEHOLDERS)
    print(f"当前：status=`{status}`" + (f"，phase=`{slug}`" if slug else ""))
    if status == "idle":
        if ctx_is_template:
            print("下一步 → `harness bootstrap`：开 bootstrap-context phase，让 agent 读代码库填 CONTEXT/DECISIONS/STATE")
        else:
            print("下一步 → `harness task \"<目标>\" [--branch]`：带目标开一个有界任务")
            print("   或 → `harness recall <keyword>` 查历史 / `harness check` 自检")
    elif status == "compact":
        print("下一步 → review `.harness/phases/current/HANDOFF.md`，然后 `harness phase archive` 归档回 idle")
    else:  # 活动态
        print("推进中 → `harness phase checkpoint --status <state> --note \"...\"` 记进度")
        print("完成后 → `harness phase compact` 压成 handoff，再 `harness phase archive`")
    return 0


def phase_checkpoint(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    ensure_initialized(root)
    state = parse_state(root / ".harness/state.yml")
    slug = state.get("phase.slug") or "current"
    status_value = args.status or state.get("phase.status") or "execute"
    if status_value not in PHASE_STATES:
        print(f"无效 phase status：{status_value}")
        return 1
    note = args.note or "Checkpoint recorded."
    timestamp = utc_now()
    append_text(root / ".harness/phases/current/EVIDENCE.md", f"## Checkpoint {timestamp}\n\n- Status: `{status_value}`\n- Note: {note}")
    progress = root / ".harness/phases/current/PROGRESS.yml"
    append_text(progress, f"checkpoint:\n  at: \"{timestamp}\"\n  status: \"{status_value}\"\n  note: \"{escape_yaml(note)}\"")
    update_state(root, **{"phase.status": status_value, "phase.slug": slug})
    print(f"已记录 checkpoint：{slug} -> {status_value}")
    return 0


def phase_compact(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    ensure_initialized(root)
    state = parse_state(root / ".harness/state.yml")
    slug = state.get("phase.slug") or "current"
    current = root / ".harness/phases/current"
    summary = compact_summary(root, slug)
    write_text(current / "HANDOFF.md", summary)
    write_text(root / "docs/ai-harness/STATE.md", short_state_after_compact(slug))
    update_state(root, **{"phase.status": "compact", "phase.slug": slug})
    print(f"已 compact phase：{slug}")
    return 0


def phase_archive(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    ensure_initialized(root)
    state = parse_state(root / ".harness/state.yml")
    slug = slugify(args.slug or state.get("phase.slug") or "phase")
    date_prefix = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    archive_root = root / ".harness/phases/archive"
    archive_dir = unique_archive_dir(archive_root / f"{date_prefix}-{slug}")
    current = root / ".harness/phases/current"
    archive_dir.mkdir(parents=True, exist_ok=True)
    for file_name in CURRENT_FILES:
        src = current / file_name
        if src.exists():
            shutil.move(str(src), str(archive_dir / file_name))
    write_text(archive_dir / "SUMMARY.md", archive_summary(archive_dir, slug))
    for file_name, content in {
        "PLAN.md": current_plan(),
        "PROGRESS.yml": progress_yml(),
        "EVIDENCE.md": evidence_doc(),
        "HANDOFF.md": handoff_doc(),
    }.items():
        write_text(current / file_name, content)
    update_state(root, **{"phase.status": "idle", "phase.slug": ""})
    write_text(root / "docs/ai-harness/STATE.md", state_doc(parse_state(root / ".harness/state.yml").get("project.name") or root.name))
    print(f"已 archive phase：{archive_dir.relative_to(root)}")
    print("  note: STATE.md 已重置为 idle；跨版本进度请确认记在 ROADMAP.md（STATE 不留存历史）")
    branch = current_git_branch(root)
    if branch and branch.startswith(PHASE_BRANCH_PREFIX):
        # G1：不自动切回/merge，只提示（选项 1 的边界）。
        print(f"  git: 你仍在 phase 分支 {branch}，记得 merge 回主干或切回")
    return 0


def recall(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    query = args.keyword.lower()
    paths = list((root / ".harness/phases/archive").glob("**/*")) + list((root / ".harness/memory").glob("**/*"))
    matches = 0
    for path in paths:
        if not path.is_file():
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for number, line in enumerate(lines, start=1):
            if query in line.lower():
                print(f"{path.relative_to(root)}:{number}: {line}")
                matches += 1
                if matches >= args.limit:
                    return 0
    if matches == 0:
        print("未找到匹配内容")
    return 0


def migrate(args: argparse.Namespace) -> int:
    """把既有库的旧命名文件 rename 到新结构，避免与 init 产生重复文件。

    安全策略：仅当「旧文件存在且新文件不存在」才 move；新旧并存时报冲突，绝不自动覆盖。
    默认 dry-run 预览，--apply 才执行。建议先 migrate 再 init。
    """
    root = Path(args.root).resolve()
    moves: list[tuple[str, str]] = []
    conflicts: list[tuple[str, str]] = []
    for old_rel, new_rel in MIGRATIONS:
        old = root / old_rel
        if not old.exists():
            continue
        if (root / new_rel).exists():
            conflicts.append((old_rel, new_rel))
        else:
            moves.append((old_rel, new_rel))

    advisories = [(old_rel, hint) for old_rel, hint in MIGRATION_ADVISORIES if (root / old_rel).exists()]

    # 遗留布局：.claude/skills/ai-harness 是真实文件/目录（非软链）-> 迁到 .agents/ 并改软链。
    link_dir = root / SKILL_LINK_DIR
    canon_dir = root / SKILL_CANONICAL_DIR
    legacy_skill = link_dir.exists() and not link_dir.is_symlink()
    legacy_cursor = root / LEGACY_CURSOR_SKILL_DIR
    legacy_cursor_copy = legacy_cursor.exists() and not legacy_cursor.is_symlink()

    if not moves and not conflicts and not advisories and not legacy_skill and not legacy_cursor_copy:
        print("未发现可迁移的旧文件")
        return 0

    apply = args.apply
    prefix = "" if apply else "[dry-run] "
    if moves:
        print(prefix + "迁移（旧 -> 新）：")
        for old_rel, new_rel in moves:
            print(f"  - {old_rel} -> {new_rel}")
            if apply:
                dest = root / new_rel
                ensure_dir(dest.parent)
                shutil.move(str(root / old_rel), str(dest))
    if legacy_skill:
        print(prefix + f"skill 收敛到唯一来源：{SKILL_LINK_DIR} -> {SKILL_CANONICAL_DIR}（改软链）")
        if apply:
            if not canon_dir.exists():
                ensure_dir(canon_dir.parent)
                shutil.move(str(link_dir), str(canon_dir))
            else:
                # 真实来源已存在，直接丢弃遗留副本，统一改软链
                if link_dir.is_dir():
                    shutil.rmtree(link_dir)
                else:
                    link_dir.unlink()
            ensure_symlink(link_dir, canon_dir)
    if legacy_cursor_copy:
        print(prefix + f"删除遗留 Cursor skill 副本：{LEGACY_CURSOR_SKILL_DIR}（Cursor 已原生读 .agents/skills/）")
        if apply:
            shutil.rmtree(legacy_cursor)
    if conflicts:
        print("冲突（新旧都存在，需手工合并，不自动覆盖）：")
        for old_rel, new_rel in conflicts:
            print(f"  - {old_rel} 与 {new_rel} 同时存在")
    if advisories:
        print("建议手工迁移（语义需人工并入）：")
        for old_rel, hint in advisories:
            print(f"  - {old_rel} -> {hint}")
    if not apply:
        print("预览模式：加 --apply 执行 move（建议先 migrate 再 init，可保留旧内容并避免重复文件）。")
    return 0


def check(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    issues = run_checks(root)
    write_check_result(root, issues)
    print_issue_summary(issues)
    return 1 if any(issue.level == "error" for issue in issues) else 0


def _limit(state: dict[str, str], key: str, default: int, issues: list[Issue]) -> int:
    """读取 limits 阈值，非整数时 fail-closed 回退默认并 warning（N3）。"""
    raw = state.get(key)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return int(str(raw).strip())
    except ValueError:
        issues.append(Issue(
            "warning", ".harness/state.yml",
            f"{key} 非整数（{raw!r}），已回退默认 {default}",
        ))
        return default


def run_checks(root: Path) -> list[Issue]:
    issues: list[Issue] = []
    state = parse_state(root / ".harness/state.yml") if (root / ".harness/state.yml").exists() else {}
    limits = {
        "agents": _limit(state, "limits.agentsMaxLines", 180, issues),
        "state": _limit(state, "limits.stateMaxLines", 150, issues),
        "plan": _limit(state, "limits.planMaxLines", 300, issues),
        "lessons": _limit(state, "limits.lessonsMaxLines", 200, issues),
    }
    for file_name in ("AGENTS.md", "CLAUDE.md"):
        path = root / file_name
        if path.exists() and count_lines(path) > limits["agents"]:
            issues.append(Issue("warning", file_name, f"入口文件超过 {limits['agents']} 行"))
    state_md = root / "docs/ai-harness/STATE.md"
    if state_md.exists() and count_lines(state_md) > limits["state"]:
        issues.append(Issue("warning", "docs/ai-harness/STATE.md", f"STATE.md 超过 {limits['state']} 行"))
    plan = root / ".harness/phases/current/PLAN.md"
    if plan.exists() and count_lines(plan) > limits["plan"]:
        issues.append(Issue("warning", ".harness/phases/current/PLAN.md", f"PLAN.md 超过 {limits['plan']} 行"))
    lessons = root / ".harness/memory/lessons.md"
    if lessons.exists() and count_lines(lessons) > limits["lessons"]:
        issues.append(Issue(
            "warning", ".harness/memory/lessons.md",
            f"lessons.md 超过 {limits['lessons']} 行，建议晋升长期项到 docs/ 或归档到 phases/archive",
        ))

    issues.extend(check_index_links(root))
    issues.extend(check_state_consistency(root, state))
    issues.extend(check_schema_version(root, state))
    issues.extend(check_context_filled(root))
    check_stale_phase(root, state, issues)
    issues.extend(check_required_sections(root, state))
    issues.extend(check_layering(root))
    issues.extend(check_skill_symlink(root))
    issues.extend(check_legacy_cursor_copy(root))
    return issues


def check_legacy_cursor_copy(root: Path) -> list[Issue]:
    """v0.8 遗留的 .cursor/skills/ 复制副本；Cursor 已原生读 .agents/skills/。"""
    legacy = root / LEGACY_CURSOR_SKILL_DIR
    if not legacy.exists() or legacy.is_symlink():
        return []
    return [Issue(
        "warning", LEGACY_CURSOR_SKILL_DIR,
        "遗留 v0.8 Cursor skill 副本（多余），Cursor 已原生读 .agents/skills/，"
        "建议删除；可运行 `harness migrate --apply` 清理",
    )]


def check_skill_symlink(root: Path) -> list[Issue]:
    """校验 .claude skill 软链：断裂报 error，退化为普通副本报 warning。"""
    issues: list[Issue] = []
    link_dir = root / SKILL_LINK_DIR
    canon = root / SKILL_CANONICAL_DIR
    if link_dir.is_symlink():
        if not link_dir.exists():
            issues.append(Issue("error", SKILL_LINK_DIR, "skill 软链断裂（目标缺失）"))
    elif link_dir.exists() and canon.exists():
        issues.append(Issue(
            "warning", SKILL_LINK_DIR,
            "skill 已退化为副本（symlink 不可用），需手动与 .agents/ 同步",
        ))
    return issues


# INDEX 可引用、但属于运行时产物（gitignore）的路径：fresh clone / CI checkout 不存在属正常，不校验存在性。
INDEX_RUNTIME_EXEMPT = {".harness/checks/latest.json"}


def check_index_links(root: Path) -> list[Issue]:
    issues: list[Issue] = []
    index = root / "docs/ai-harness/INDEX.md"
    if not index.exists():
        return issues
    text = read_text(index)
    seen: set[str] = set()
    for candidate in collect_index_paths(text):
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate in INDEX_RUNTIME_EXEMPT:
            continue
        if not (root / candidate).exists():
            issues.append(Issue("error", "docs/ai-harness/INDEX.md", f"引用路径不存在：{candidate}"))
    return issues


def collect_index_paths(text: str) -> list[str]:
    """从 INDEX.md 收集需要校验存在性的本地路径：反引号路径 + markdown 链接目标。"""
    paths: list[str] = []
    # 反引号内的相对路径（保持原语义：含空格的说明性 span 跳过）
    for raw in re.findall(r"`([^`\n]+)`", text):
        if " " in raw:
            continue
        if is_local_path(raw):
            paths.append(raw)
    # markdown 链接 [text](target)，去掉可选 title 与 fragment/query
    for raw in re.findall(r"\]\(([^)]+)\)", text):
        parts = raw.strip().split()
        if not parts:
            continue
        target = parts[0].split("#", 1)[0].split("?", 1)[0]
        if is_local_path(target):
            paths.append(target)
    return paths


def is_local_path(value: str) -> bool:
    """判断是否是需要校验存在性的仓库内相对路径（排除外链、anchor、绝对路径、非路径 token）。"""
    value = value.strip()
    if not value:
        return False
    if value.startswith(("http://", "https://", "mailto:", "#", "/", "~")):
        return False
    if any(ch in value for ch in ("*", ":", "\n", "`", " ", "<", ">")):
        return False
    return True


# G5：required-sections 空壳检测。占位串与 current_plan()/evidence_doc() 同源，
# 由 test_required_section_placeholders_match_templates 守护，模板改动会让该测试变红。
REQUIRED_SECTIONS = {
    ".harness/phases/current/PLAN.md": {
        "headings": ("## Goal", "## Acceptance Criteria"),
        # 用模板独有的高区分度片段，避免 PLAN 正文"讨论占位符"时误命中（本 phase 即踩过）。
        "placeholders": ("做完什么算完成", "路径具体到可被 subagent 直接定位"),
    },
    # EVIDENCE 早期（discover/design）本就没验证内容，只查 heading 存在，不查占位符（避免早期误吵）。
    ".harness/phases/current/EVIDENCE.md": {
        "headings": ("## Verify Checklist",),
        "placeholders": (),
    },
}


def _parse_ts(value: str | None) -> datetime | None:
    """解析 ISO 时间戳；无法解析返回 None（fail-soft）。"""
    try:
        return datetime.fromisoformat(value) if value else None
    except (ValueError, TypeError):
        return None


def _latest_checkpoint_ts(root: Path) -> datetime | None:
    """从 PROGRESS.yml 的 checkpoint 块取最新 at: 时间。"""
    progress = root / ".harness/phases/current/PROGRESS.yml"
    if not progress.exists():
        return None
    times = []
    for line in read_text(progress).splitlines():
        stripped = line.strip()
        if stripped.startswith("at:"):
            ts = _parse_ts(clean_scalar(stripped.split(":", 1)[1]))
            if ts:
                times.append(ts)
    return max(times) if times else None


def check_stale_phase(root: Path, state: dict[str, str], issues: list[Issue]) -> None:
    """活动态 phase 太久没 checkpoint → warning（G5）。

    参考时间 = max(startedAt, 最新 checkpoint)；now - 参考 > limits.stalePhaseDays（默认 7）。
    fail-soft：时间无法解析则跳过，不误报、不崩。
    """
    if (state.get("phase.status") or "idle") not in ACTIVE_PHASE_STATES:
        return
    started = _parse_ts(state.get("phase.startedAt"))
    latest_cp = _latest_checkpoint_ts(root)
    ref = max([t for t in (started, latest_cp) if t], default=None)
    if ref is None:
        return
    days = _limit(state, "limits.stalePhaseDays", 7, issues)
    age = datetime.now(timezone.utc) - ref
    if age.total_seconds() > days * 86400:
        slug = state.get("phase.slug") or "current"
        issues.append(Issue(
            "warning", ".harness/state.yml",
            f"phase `{slug}` 已 {age.days} 天无 checkpoint（阈值 {days}），建议 checkpoint 或 compact",
        ))


def check_required_sections(root: Path, state: dict[str, str]) -> list[Issue]:
    """活动态 phase 的 PLAN/EVIDENCE 空壳检测（G5）：缺必备 heading 或关键 section 仍是模板占位 → warning。"""
    issues: list[Issue] = []
    if (state.get("phase.status") or "idle") == "idle":
        return issues
    for rel, spec in REQUIRED_SECTIONS.items():
        path = root / rel
        if not path.exists():
            continue  # 文件缺失由 check_state_consistency 报 error
        text = read_text(path)
        for heading in spec["headings"]:
            if heading not in text:
                issues.append(Issue("warning", rel, f"缺少必备 section「{heading}」"))
        for placeholder in spec["placeholders"]:
            if placeholder in text:
                issues.append(Issue(
                    "warning", rel,
                    f"section 仍是模板占位（含「{placeholder}」），phase 可能是空壳",
                ))
    return issues


def check_context_filled(root: Path) -> list[Issue]:
    """bootstrap nudge：CONTEXT.md 仍是 init 模板占位 → warning，提示跑 `harness bootstrap`。"""
    issues: list[Issue] = []
    ctx = root / "docs/ai-harness/CONTEXT.md"
    if ctx.exists() and any(p in read_text(ctx) for p in CONTEXT_PLACEHOLDERS):
        issues.append(Issue(
            "warning", "docs/ai-harness/CONTEXT.md",
            "CONTEXT 仍是模板占位，运行 `harness bootstrap` 让 agent 从代码库填充首次上下文",
        ))
    return issues


def check_schema_version(root: Path, state: dict[str, str]) -> list[Issue]:
    """兑现 README §5：state / config 的 schemaVersion 落后于当前 → warning。

    落后是"该升级"而非"坏状态"，用 warning 不用 error（避免 CI/hook 过激拦截）；
    提示用户跑 `harness upgrade --apply` 对齐。
    """
    issues: list[Issue] = []
    targets: list[tuple[str, str | None]] = [(".harness/state.yml", state.get("schemaVersion"))]
    config_path = root / ".harness/config.yml"
    if config_path.exists():
        targets.append((".harness/config.yml", parse_state(config_path).get("schemaVersion")))
    for rel, ver in targets:
        if ver and str(ver) != str(SCHEMA_VERSION):
            issues.append(Issue(
                "warning", rel,
                f"schemaVersion {ver} ≠ 当前 {SCHEMA_VERSION}，运行 `harness upgrade --apply` 对齐",
            ))
    return issues


def check_state_consistency(root: Path, state: dict[str, str]) -> list[Issue]:
    issues: list[Issue] = []
    state_path = root / ".harness/state.yml"
    if not state_path.exists():
        issues.append(Issue("error", ".harness/state.yml", "state 文件缺失"))
        return issues
    status_value = state.get("phase.status") or "idle"
    slug = state.get("phase.slug") or ""
    current = root / ".harness/phases/current"
    if status_value not in PHASE_STATES:
        issues.append(Issue("error", ".harness/state.yml", f"无效 phase status：{status_value}"))
    if status_value != "idle":
        for file_name in CURRENT_FILES:
            if not (current / file_name).exists():
                issues.append(Issue("error", f".harness/phases/current/{file_name}", "active phase 文件缺失"))
        if not slug:
            issues.append(Issue("error", ".harness/state.yml", "active phase 的 slug 为空"))
    if status_value == "compact":
        issues.append(Issue("warning", ".harness/state.yml", "phase 已 compact 但尚未 archive"))
    return issues


def check_layering(root: Path) -> list[Issue]:
    issues: list[Issue] = []
    machine_patterns = ("schemaVersion:", "currentPath:", "startedAt:")
    for path in (root / "docs").glob("**/*.md") if (root / "docs").exists() else []:
        text = read_text(path)
        if any(pattern in text for pattern in machine_patterns):
            issues.append(Issue("warning", str(path.relative_to(root)), "docs/ 包含 machine-state 字段"))
    human_policy_patterns = (
        "# Harness Policies",
        "## Core Harness Policy",
        "## 工程基线",
        "## Java/Spring Profile",
    )
    for path in (root / ".harness").glob("**/*.md") if (root / ".harness").exists() else []:
        text = read_text(path)
        if any(pattern in text for pattern in human_policy_patterns):
            issues.append(Issue("warning", str(path.relative_to(root)), ".harness/ 包含疑似 policy 正文"))
    return issues


def write_check_result(root: Path, issues: list[Issue], dry_run: bool = False) -> None:
    payload = {
        "generatedAt": utc_now(),
        "summary": {
            "errors": sum(1 for issue in issues if issue.level == "error"),
            "warnings": sum(1 for issue in issues if issue.level == "warning"),
        },
        "issues": [issue.__dict__ for issue in issues],
    }
    write_text(root / ".harness/checks/latest.json", json.dumps(payload, ensure_ascii=False, indent=2) + "\n", dry_run=dry_run)


def print_issue_summary(issues: list[Issue]) -> None:
    errors = [issue for issue in issues if issue.level == "error"]
    warnings = [issue for issue in issues if issue.level == "warning"]
    print(f"check: {len(errors)} error(s), {len(warnings)} warning(s)")
    for issue in issues:
        print(f"  [{issue.level}] {issue.path}: {issue.message}")


def count_lines(path: Path) -> int:
    return len(read_text(path).splitlines())


def first_lines(path: Path, limit: int) -> str:
    return "\n".join(read_text(path).splitlines()[:limit])


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-").lower()
    if not slug:
        raise SystemExit("slug 不能为空")
    return slug


def ensure_initialized(root: Path) -> None:
    if not (root / ".harness/state.yml").exists():
        raise SystemExit("harness 尚未初始化；请先运行 `harness init`")


def escape_yaml(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def compact_summary(root: Path, slug: str) -> str:
    return f"""# Handoff: {slug}

生成时间：`{utc_now()}`

> compact 骨架：请由 agent 按"先最大召回、再提精度"填写以下字段；不要留 `<!-- 待填写 -->`。
> 源材料：`.harness/phases/current/PLAN.md`、`.harness/phases/current/EVIDENCE.md`。

## 恢复说明

- 先读 `docs/ai-harness/STATE.md`、`docs/ai-harness/CONTEXT.md`、`docs/ai-harness/DECISIONS.md`。
- 继续 phase `{slug}` 前读取本 handoff。
- verification 完成后 archive 本 phase。

## 已确认决策

- <!-- 待填写：本 phase 形成且仍生效的 decision -->

## 改动的文件 / 接口

- <!-- 待填写：具体路径，便于下一段直接定位 -->

## 未解决风险 / 阻塞

- <!-- 待填写：当时不起眼但后续可能要命的上下文 -->

## 验证命令与结果

- <!-- 待填写：可运行命令 + 关键真实输出 -->

## 下一步

- <!-- 待填写：恢复后第一件事 -->
"""


def short_state_after_compact(slug: str) -> str:
    return f"""# 当前状态

## Phase

- Status: `compact`
- Current phase: `{slug}`
- Next action: review `.harness/phases/current/HANDOFF.md`，然后运行 `harness phase archive`。

## 验证

- 运行 `harness check`。
"""


def unique_archive_dir(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(2, 100):
        candidate = Path(f"{path}-{index}")
        if not candidate.exists():
            return candidate
    raise SystemExit(f"同名 archive 目录过多：{path.name}")


def archive_summary(archive_dir: Path, slug: str) -> str:
    handoff = archive_dir / "HANDOFF.md"
    handoff_excerpt = first_lines(handoff, 60) if handoff.exists() else "未捕获 handoff。"
    return f"""# Archive Summary: {slug}

归档时间：`{utc_now()}`

## Handoff 摘要

{handoff_excerpt}
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="harness")
    parser.add_argument("--version", action="version", version=f"harness {__version__}")
    parser.add_argument("--root", default=".", help="target project root")
    sub = parser.add_subparsers(dest="command", required=True)

    init_cmd = sub.add_parser("init")
    init_cmd.add_argument("--profile", choices=("core", "java-spring"), default="core")
    init_cmd.add_argument("--agent", default="codex,claude")
    init_cmd.add_argument("--project-name")
    init_cmd.add_argument("--with-hooks", action="store_true")
    init_cmd.add_argument("--with-commands", action="store_true",
                          help="在 .claude/commands/ 生成 harness-* slash command 模板（默认关）")
    init_cmd.add_argument("--dry-run", action="store_true")
    init_cmd.set_defaults(func=init_harness)

    upgrade_cmd = sub.add_parser("upgrade")
    upgrade_cmd.add_argument("--apply", action="store_true")
    upgrade_cmd.add_argument("--refresh-infra", action="store_true")
    upgrade_cmd.add_argument("--with-hooks", action="store_true")
    upgrade_cmd.add_argument("--with-commands", action="store_true",
                             help="在 .claude/commands/ 生成 harness-* slash command 模板（默认关）")
    upgrade_cmd.set_defaults(func=upgrade)

    doctor_cmd = sub.add_parser("doctor")
    doctor_cmd.set_defaults(func=doctor)

    bootstrap_cmd = sub.add_parser("bootstrap")
    bootstrap_cmd.add_argument("--profile", choices=("core", "java-spring"), default="core",
                               help="未 init 时用的 profile")
    bootstrap_cmd.add_argument("--agent", default="codex,claude", help="未 init 时用的 agent 列表")
    bootstrap_cmd.set_defaults(func=bootstrap)

    task_cmd = sub.add_parser("task")
    task_cmd.add_argument("goal", help="任务目标（一句话；会预填进 PLAN 的 Goal）")
    task_cmd.add_argument("--slug", help="phase slug（默认从 goal 派生，纯中文则回退 task）")
    task_cmd.add_argument("--branch", action="store_true", help="opt-in：创建/切换到 phase/<slug> 分支")
    task_cmd.set_defaults(func=task)

    next_cmd = sub.add_parser("next")
    next_cmd.set_defaults(func=next_step)

    status_cmd = sub.add_parser("status")
    status_cmd.set_defaults(func=status)

    phase = sub.add_parser("phase")
    phase_sub = phase.add_subparsers(dest="phase_command", required=True)
    start = phase_sub.add_parser("start")
    start.add_argument("slug")
    start.add_argument("--branch", action="store_true",
                       help="opt-in：创建/切换到 phase/<slug> 分支（G1，fail-soft）")
    start.set_defaults(func=phase_start)
    checkpoint = phase_sub.add_parser("checkpoint")
    checkpoint.add_argument("--status", choices=PHASE_STATES)
    checkpoint.add_argument("--note")
    checkpoint.set_defaults(func=phase_checkpoint)
    compact = phase_sub.add_parser("compact")
    compact.set_defaults(func=phase_compact)
    archive = phase_sub.add_parser("archive")
    archive.add_argument("slug", nargs="?")
    archive.set_defaults(func=phase_archive)

    recall_cmd = sub.add_parser("recall")
    recall_cmd.add_argument("keyword")
    recall_cmd.add_argument("--limit", type=int, default=50)
    recall_cmd.set_defaults(func=recall)

    migrate_cmd = sub.add_parser("migrate")
    migrate_cmd.add_argument("--apply", action="store_true")
    migrate_cmd.set_defaults(func=migrate)

    check_cmd = sub.add_parser("check")
    check_cmd.set_defaults(func=check)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
