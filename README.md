# ai-harness

[![CI](https://github.com/Xavier189/ai-harness/actions/workflows/ci.yml/badge.svg)](https://github.com/Xavier189/ai-harness/actions/workflows/ci.yml)

> 轻量、**单文件、零依赖**的仓库级 AI 协作 harness。给任何项目装上一套「人读 `docs/` 与机器 `.harness/` 分层 + 有界 phase + compact→archive→recall」的协作骨架，让 AI agent **跨 session 可恢复、上下文不膨胀**。

---

## 目录

1. [它解决什么问题](#它解决什么问题)
2. [30 秒看懂：四条核心理念](#30-秒看懂四条核心理念)
3. [快速开始](#快速开始)
4. [命令参考](#命令参考)
5. [**实现原理（重点）**](#实现原理重点)
   - [空仓库 `init` 会生成什么](#1-空仓库-init-会生成什么)
   - [每个生成文件的作用](#2-每个生成文件的作用)
   - [一个 phase 的完整生命周期](#3-一个-phase-的完整生命周期)
   - [`state.yml` 如何驱动一切](#4-stateyml-如何驱动一切)
   - [`check` 校验什么](#5-check-校验什么)
   - [跨工具：一份来源，多处复用](#6-跨工具一份来源多处复用)
6. [本仓库自身结构](#本仓库自身结构)
7. [设计依据](#设计依据)
8. [版本进度与路线](#版本进度与路线)
9. [开发](#开发)

---

## 它解决什么问题

AI coding agent 最大的约束是**上下文窗口**：会满、会被无关信息污染、跨 session 会"失忆"。结果是——同一个项目，换个 session 就得重新解释一遍背景；聊久了 agent 开始忘记早先的决策；重要的"为什么这么做"散落在聊天记录里，关掉就没了。

`ai-harness` 把这件事**结构化**：

- **稳定的规范/决策/上下文** → 沉淀到 `docs/`（人读）。
- **机器状态 + 当前这段有边界的工作** → 放到 `.harness/`（机器态）。
- **完成的工作** → 先 compact 成高保真摘要，再 archive 归档；默认不加载，需要时 `recall` 检索。

新 session 只需读少量「高信号」入口文件，就能**带着记忆继续**，而不是从零开始。

---

## 30 秒看懂：四条核心理念

| # | 理念 | 怎么落地 |
|---|---|---|
| 1 | **人读 / 机器分层** | `docs/` 放规范决策，`.harness/` 放机器态；`harness check` 强制这条边界不被污染 |
| 2 | **有界上下文** | 工作落在一个 phase；做完即 compact→archive，靠 `recall` 检索而非默认全量加载 |
| 3 | **可暂停 / 可恢复** | `state.yml` 是 phase 的机器 source of truth；checkpoint / HANDOFF 让任意 session「继续」 |
| 4 | **可选、可回退、不增加启动负担** | 所有能力默认 opt-in（hook、commands 都要显式开关）；单文件零依赖 |

---

## 快速开始

**安装**（任选其一，让 `harness` 命令进 PATH）：

```bash
uv tool install ai-harness        # 推荐：常驻安装（uv 用户）
pipx install ai-harness           # 或 pipx
# 未发布到 PyPI 前，从 git 直接装：
#   uv tool install git+https://github.com/<你>/ai-harness
#   pipx install git+https://github.com/<你>/ai-harness
```

**在你的项目里用**（装好后 `harness` 是普通命令，任何目录可用）：

```bash
cd ~/my-project
harness init --agent codex,claude   # 在当前项目生成骨架
harness check                       # 卫生自检，应 0 error
harness status                      # 看当前 phase
```

**懒得安装？一行 `uvx` 跑完即走**（无需预装、无需 clone、不留常驻）：

```bash
uvx --from git+https://github.com/<你>/ai-harness ai-harness init --agent claude
# 或从本地仓库路径：
uvx --from /path/to/ai-harness ai-harness init --agent claude
```

> 也可不安装直接跑源码：`python3 /path/to/ai-harness/ai_harness.py init ...`（单文件零依赖，仅需 Python 3.9+）。

**已有代码仓库首次接入**（不是空项目）：`init` 只做加法、不碰你的源码、不覆盖已存在文件；随后用 `bootstrap` 让 AI agent 把人读层从代码库填成真实内容：

```bash
cd ~/existing-repo
harness init --agent codex,claude   # 安全铺骨架（幂等，只新增 harness 文件）
harness bootstrap                    # 开 bootstrap-context phase：引导 agent 读代码库
# → 让 AI agent 按 .harness/phases/current/PLAN.md 填 CONTEXT/DECISIONS/STATE
harness check                        # CONTEXT 仍是模板会 warning 提示；填好后 warning 消失
```

> `check` 在 CONTEXT 未填时会主动提示「运行 `harness bootstrap`」——这就是"触发首次初始化"的信号。CLI 只铺确定性脚手架，读代码 synthesize 上下文由 agent 完成。多个关联仓库：**每仓独立一套 harness**，跨仓契约对称写进两边 CONTEXT。

**已有旧版 harness 文件的项目**：先 `migrate` 再 `init`，保留旧内容、避免重复：

```bash
harness migrate          # dry-run 预览要 rename 什么
harness migrate --apply  # 执行 rename（新旧并存只报冲突，绝不覆盖）
harness init --agent codex,claude
```

---

## 命令参考

| 命令 | 作用 |
|---|---|
| `init [--profile core\|java-spring] [--agent codex,claude] [--with-hooks] [--with-commands] [--dry-run]` | 初始化分层骨架 + 装 skill（+ 可选 Stop hook / slash commands） |
| `bootstrap [--profile ...] [--agent ...]` | 已有代码仓库首次接入：确保 init → 开 `bootstrap-context` phase 引导 agent 读代码库填 CONTEXT/DECISIONS/STATE（未 init 则先自动 init） |
| `upgrade [--apply] [--refresh-infra] [--with-hooks] [--with-commands]` | 已有库对齐到当前模板：补齐缺失文件 + bump schemaVersion（默认 dry-run，不覆盖用户内容） |
| `migrate [--apply]` | 既有库旧文件名 → 新结构安全 rename（默认 dry-run；新旧并存只报冲突） |
| `phase start <slug> [--branch]` | 开一个有边界的 phase（`--branch` 顺带创建/切换到 `phase/<slug>` 分支，opt-in、fail-soft） |
| `phase checkpoint --status <state> --note "<note>"` | 记录进度（写 EVIDENCE + PROGRESS） |
| `phase compact` | 收尾前压缩成高保真 HANDOFF 摘要 |
| `phase archive` | 归档 current/ 到 archive/，回到 idle（在 `phase/` 分支时提示 merge/切回） |
| `recall <keyword>` | 从 archive / memory 检索关键词 |
| `status` / `doctor` / `check` / `--version` | 看当前 phase / 环境体检 / 卫生自检 / 打印版本 |

合法 phase status：`idle, discover, discuss, design, plan, execute, verify, compact, archive`。

### 命令在哪执行？（shell CLI，agent 通过 shell 调用）

`harness` 是一个**普通的 shell CLI**——永远在终端里跑，不是某个 coding agent 的内置命令。三种用法：

| 谁在跑 | 怎么跑 |
|---|---|
| **你（人）** | 在终端直接敲 `harness next`；或在 Claude Code 输入框用 `!harness next` 内联执行 |
| **coding agent**（Claude Code / Codex / Cursor） | agent 通过它自己的「运行终端命令」能力执行 `harness ...`。`SKILL.md` 会告诉 agent 何时该跑哪个——这是**跨三工具统一**的机制（本质就是"跑一条 shell 命令"） |
| **可选：Claude slash 命令** | `init --with-commands` 会生成 `.claude/commands/harness-{phase,recall,check}.md`，在 Claude Code 里可 `/harness-phase` 调用。**仅 Claude、可选糖**，非必需 |

心智模型：**CLI 是确定性工具；SKILL.md 让 agent 知道去跑它；agent 用 shell 跑。** 不需要给每个工具做一套原生命令——一份 CLI + 一份 skill 就跨工具通用。

---

## 实现原理（重点）

这一节回答：**命令到底生成/改了什么？空仓库跑一遍会变成什么样？**

### 1. 空仓库 `init` 会生成什么

在一个空目录执行 `harness init --agent codex,claude`，会生成这棵树（**全部是普通文本文件，无任何二进制/依赖**）：

```text
你的项目/
├── AGENTS.md                 # Codex 入口：只插一个受管理的 ROUTER block
├── CLAUDE.md                 # Claude 入口：同上（块外内容永不被动）
│
├── docs/
│   ├── ai-harness/           # 👁 人读层：规范 / 决策 / 上下文
│   │   ├── README.md         #   这层的说明
│   │   ├── STATE.md          #   当前短状态（phase / 焦点 / 下一步）
│   │   ├── CONTEXT.md        #   稳定项目地图、领域语言、架构边界
│   │   ├── DECISIONS.md      #   仍然有效的决策索引
│   │   ├── POLICIES.md       #   工程与协作 policy（按需加载，不进入口文件）
│   │   ├── ROADMAP.md        #   项目级 numbered phases + backlog
│   │   ├── OUT-OF-SCOPE.md   #   项目级「明确不做」+ 重审条件
│   │   └── INDEX.md          #   人读 artifact 索引（check 会校验这里的链接）
│   ├── adr/0000-template.md  #   ADR 模板（复制为 NNNN-<slug>.md 新建决策记录）
│   └── design/               #   （预留）设计草稿
│
├── .harness/                 # ⚙️ 机器层：状态 / 当前工作 / 归档 / 检索
│   ├── config.yml            #   项目配置（name / profile / agents / paths）
│   ├── state.yml             #   ⭐ phase 的机器 source of truth
│   ├── phases/
│   │   ├── current/          #   当前活跃 phase 的工作文件
│   │   │   ├── PLAN.md        #     自包含 spec（涉及文件 / out-of-scope / 验证）
│   │   │   ├── PROGRESS.yml   #     机器可读 checkpoint 列表
│   │   │   ├── EVIDENCE.md    #     人读验证证据 + Verify Checklist
│   │   │   └── HANDOFF.md     #     compact 时生成的恢复摘要
│   │   └── archive/          #   归档的历史 phase（默认不读，靠 recall）
│   ├── checks/latest.json    #   最近一次 check 的结果
│   └── memory/
│       ├── lessons.md        #   结构化经验沉淀（超阈值 check 会提醒精简）
│       └── topics/           #   （预留）按主题组织的 memory
│
└── .agents/
    └── skills/ai-harness/
        └── SKILL.md          # ⭐ skill 唯一真实来源（Codex / Cursor 原生扫此目录）
```

加 `--agent claude` 时还会多一个**软链**（不是副本）：

```text
.claude/skills/ai-harness  →  ../../.agents/skills/ai-harness   (symlink)
```

可选开关：

- `--with-hooks` → 生成 `.claude/settings.json`，注入 Stop hook：agent 停止前自动跑 `harness check`。
- `--with-commands` → 生成 `.claude/commands/harness-{phase,recall,check}.md` 三个 slash command 模板。

> **Cursor**：与 Codex 一样原生扫描 `.agents/skills/`，无需额外副本或开关。

> **幂等**：再跑一次 `init` 不会重复写、不会覆盖你改过的内容——已存在的文件直接跳过。

### 2. 每个生成文件的作用

分两层，边界由 `check` 强制（**docs/ 不准混入机器字段，.harness/ 不准混入 policy 正文**）：

| 文件 | 层 | 它装什么 | 谁来写 |
|---|---|---|---|
| `AGENTS.md` / `CLAUDE.md` | 入口 | 只一个 ROUTER block 告诉 agent「先读哪几个文件」；保持极短 | CLI 管理 block，块外归你 |
| `docs/ai-harness/STATE.md` | 人读 | 当前在做什么、下一步、阻塞 | 你 / agent |
| `docs/ai-harness/CONTEXT.md` | 人读 | 不变的项目地图、领域语言、架构 | 你 / agent |
| `docs/ai-harness/DECISIONS.md` | 人读 | 仍有效的决策（一句话 + 指针） | 你 / agent |
| `docs/ai-harness/POLICIES.md` | 人读 | 工程基线、协作模式（按需读，不塞入口） | 模板 + 你追加 |
| `.harness/state.yml` | 机器 | phase 状态、context 加载清单、行数阈值 | **CLI 独占** |
| `.harness/phases/current/*` | 机器 | 当前 phase 的 plan / 进度 / 证据 / 交接 | CLI 起骨架，agent 填 |
| `.agents/skills/ai-harness/SKILL.md` | skill | 教 agent 怎么用本 harness（自动触发） | 模板 |

### 3. 一个 phase 的完整生命周期

一段有边界的工作 = 一个 phase。命令如何改变文件状态：

```text
  harness phase start fix-login
        │   state.yml: status idle→discover, slug="fix-login", startedAt=now
        │   PLAN.md  : 重置为 "Phase Plan: fix-login" 的自包含 spec 骨架
        ▼
  harness phase checkpoint --status execute --note "登录接口已修，待加测试"
        │   EVIDENCE.md : 追加 "## Checkpoint <时间>"（人读证据）
        │   PROGRESS.yml: 追加一条 {at, status, note}（机器可读）
        │   state.yml   : status→execute
        │   HANDOFF.md  : ❗不动（v0.5 起 checkpoint 不再污染 HANDOFF）
        ▼   （可多次 checkpoint）
  harness phase compact
        │   HANDOFF.md : 生成结构化高保真摘要骨架（决策/改动文件/未决风险/
        │                验证命令/下一步），由 agent「先召回再精度」填写
        │   STATE.md   : 更新为 compact 状态
        │   state.yml  : status→compact
        ▼
  harness phase archive
        │   current/ 的 4 个文件 → 移到 .harness/phases/archive/<日期>-fix-login/
        │   该归档目录写入 SUMMARY.md
        │   current/ 重置为空白模板，state.yml: status→idle, slug=""
        ▼
  （需要翻历史时）harness recall login
            从 archive/ 和 memory/ grep "login"，打印 路径:行号:原文
```

关键设计：**archive 默认不加载**，避免老 phase 撑爆上下文；只在 `recall` 命中时才把相关行捞回来。

### 4. `state.yml` 如何驱动一切

`state.yml` 是 phase 的**唯一机器真相**（12-Factor Agents #12）。其它命令读它来决定行为，新 session 读它来"知道现在在哪一步"：

```yaml
schemaVersion: 2
project:
  name: "ai-harness"
  profile: "core"
phase:
  status: idle          # ← 当前处于生命周期哪一步
  slug: ""              # ← 当前 phase 名（idle 时为空）
  startedAt: ""
  currentPath: ".harness/phases/current"
context:
  requiredRead:         # ← 新 session 必读（高信号入口）
    - docs/ai-harness/STATE.md
    - docs/ai-harness/CONTEXT.md
    - docs/ai-harness/DECISIONS.md
  optionalRead:         # ← 仅 active phase 时才读
    - .harness/phases/current/PLAN.md
limits:                 # ← check 用的行数阈值（防文档无界膨胀）
  agentsMaxLines: 180
  stateMaxLines: 150
  planMaxLines: 300
```

### 5. `check` 校验什么

`harness check` 是 harness 的自检闸门（可挂到 Stop hook 上每次自动跑）。它检查：

| 检查项 | 级别 | 含义 |
|---|---|---|
| 入口文件 / STATE / PLAN / lessons 行数超阈值 | warning | 文档在无界膨胀，该精简或归档 |
| `INDEX.md` 引用的路径不存在 | **error** | 断链 |
| `state.yml` 缺失 | **error** | 机器状态异常 |
| state / config 的 schemaVersion 落后于当前 | warning | 该 `harness upgrade --apply` 对齐 |
| `limits` 阈值非整数 | warning | 回退默认（fail-closed，不崩） |
| CONTEXT.md 仍是 init 模板占位 | warning | 未 onboarding，跑 `harness bootstrap` |
| 活动 phase 超 `stalePhaseDays`（默认 7）无 checkpoint | warning | phase 疑似停滞，该 checkpoint 或 compact |
| 活动 phase 的 PLAN 缺必备 section / 仍是模板占位 | warning | phase 可能是空壳 |
| 分层泄漏（docs/ 含机器字段、.harness/ 含 policy 正文） | warning | 违反人读/机器边界 |
| `.claude/skills` 软链断裂 / 退化为副本 | error/warning | 跨工具来源出问题 |
| 遗留 `.cursor/skills/ai-harness/` 副本（v0.8） | warning | 多余副本，建议 `harness migrate --apply` 清理 |

退出码：有 error 返回 1（CI / hook 可拦），否则 0。上表新增的 schema/limits/context/stale/空壳 检查均为 warning，不拦 CI。

### 6. 跨工具：一份来源，多处复用

不同 AI coding 工具从不同目录发现 skill，但 **SKILL.md 已是跨工具开放标准**（agentskills.io，26+ 平台）。本 harness 的策略：**`.agents/skills/` 一份真实来源，各工具按自己的发现机制接入**：

```text
                  .agents/skills/ai-harness/SKILL.md   ← 唯一真实来源
                            ▲
        ┌───────────────────┼────────────────────┐
   Codex 原生扫描         Claude 目录软链        Cursor 原生扫描
   （零成本）              .claude/skills/         （零成本，同 .agents/）
                          → 软链指回源
```

- **Codex / Cursor**：`.agents/skills/` **正好是仓库级 skills 约定**，零成本即被发现。
- **Claude Code**：`.claude/skills/ai-harness` 是相对软链，指回 `.agents/`，改一处两处生效。

> 这样无论哪个工具，skill 内容只维护**一份**，不会出现多份事实来源彼此漂移。

---

## 本仓库自身结构

本仓库**就是 `ai-harness` 工具自身**，并且 **dogfood**——用 harness 管理 harness。所以目录里既有「工具代码」，也有「工具对自己跑 init 产生的 dogfood 产物」：

| 路径 | 是什么 | 类别 |
|---|---|---|
| `ai_harness.py` | 单文件 Python3 CLI（约 1440 行，全部逻辑都在此）；`pyproject.toml` 把它暴露为 `harness` 命令 | **工具代码** |
| `tests/test_harness_cli.py` | unittest（40 tests） | **工具代码** |
| `evals/` | 声明式行为场景 runner（`run.py` + 4 个 `scenarios/*.json`） | **工具代码** |
| `skills/ai-harness-init/SKILL.md` | 给「想安装本 harness 的项目」用的 meta-skill | **工具代码** |
| `VERSIONING.md` | schemaVersion 演进与 upgrade 约定 | **工具代码** |
| `docs/REVIEW-AND-ROADMAP.md` | 设计依据与参考来源映射 | 文档 |
| `todo/` | 前瞻计划：`v0.5-plan` / `multi-tool-roadmap` / `backlog` | 文档 |
| `docs/ai-harness/`、`.harness/`、`.agents/`、`.claude/`、`AGENTS.md`、`CLAUDE.md` | **harness 对自己跑 init 的产物** | **dogfood 产物** |

> 想看「装到别的项目会长什么样」，看上面 [实现原理 §1](#1-空仓库-init-会生成什么)；本仓库根目录的 `docs/ai-harness/`、`.harness/` 等就是活生生的例子。

---

## 设计依据

`ai-harness` 不是凭空设计——从一线实践提炼，再结合业界优秀 harness「取其精华、弃其糟泊」。每个核心设计对应哪条权威依据、取了什么弃了什么，详见 **`docs/REVIEW-AND-ROADMAP.md`**。主要来源：

- Anthropic《Effective Context Engineering for AI Agents》《Claude Code Best Practices》
- 《12-Factor Agents》(HumanLayer)
- obra/Superpowers、gsd-core / Get-Shit-Done
- OpenAI Codex / agents.md / agentskills.io（跨工具标准）

明确**不抄**：enterprise ceremony（story points / sprint 仪式）、默认强制 TDD、框架膨胀。保持单文件、零依赖、轻量。

---

## 版本进度与路线

| 版本 | 主题 | 状态 |
|---|---|---|
| v0.1 | 分层骨架 + phase 状态机 + compact/archive/recall + check + profile | ✅ |
| v0.2 | 工程基线进 POLICIES、check 修链接、migrate、skill 装入、PLAN 自包含 | ✅ |
| v0.3 | 语义化 compact、upgrade+VERSIONING、可选 Stop hook、ROADMAP/ADR、结构化 memory | ✅ |
| v0.4 | `.agents/skills/` 唯一来源 + Claude 目录软链 + 回退兜底 | ✅ |
| v0.5 | 收敛 current/ 冗余、强化测试 + evals、lessons 阈值、OUT-OF-SCOPE、`--with-commands` | ✅ |
| v0.6 | AGENTS.md 指明 skill 来源 + 确认 Codex 原生支持 | ✅ |
| v0.7 | 分发打包：pyproject + console_scripts，`uvx`/`pipx`/`uv tool install` 一行安装 | ✅ |
| v0.8 | Cursor 适配：原生扫描 `.agents/skills/`（撤销复制方案） | ✅ |
| v0.9 | 修地基：state 定点更新保真用户定制、check 校验 schemaVersion/limits、`--version` 单一来源 | ✅ |
| v0.10 | 深化 check（stale phase / 空壳检测）、G1 `phase start --branch`、`bootstrap` 已有仓库首次接入 | ✅ |
| 后续 | 发布 PyPI（`uvx ai-harness` 免 --from）+ CHANGELOG | 规划中 |

> 适配范围已收敛到 **Claude / Codex / Cursor** 三个平台；Windsurf / Aider / Gemini 等**暂不做**（理由与重审条件见 `docs/ai-harness/OUT-OF-SCOPE.md`）。

详细路线见 `docs/ai-harness/ROADMAP.md`、`todo/multi-tool-roadmap.md`、`todo/v0.5-plan.md`、`todo/backlog.md`。

---

## 开发

```bash
python3 -m unittest discover -s tests   # 单测（当前 72）
python3 evals/run.py                     # 5 个行为场景
python3 ai_harness.py check              # 卫生自检，应 0 error
```

新 session 接手本项目：先读 `docs/ai-harness/STATE.md`、`CONTEXT.md`、`DECISIONS.md`（也就是上面 §1 设计里 agent 该读的那几个高信号入口）。

**维护者合并 PR**：main 受 ruleset 保护（admin 可 bypass）。用 `scripts/merge-pr.sh <pr-number>` 合并——它只在 GitHub 侧 rebase 合并，再本地确定性 `fetch + ff` 收尾，规避 `gh pr merge --delete-branch` 反复触发的本地 `origin/main` ref 竞态。

## License

TBD（建议 MIT）。
