# AI Harness — 设计依据与参考来源

> 性质：**设计依据档案**（非路线图）。记录本项目的设计提炼自哪些一线实践、取了什么、弃了什么。
> 当前版本进度看 `docs/ai-harness/ROADMAP.md`；历史实现细节看 git log。

## 这份文档解决什么

`ai-harness` 不是凭空设计的——它从一线 AI 协作实践中提炼，再结合业界优秀 harness「取其精华、弃其糟泊」。本文是那次评审的沉淀，说明**每个核心设计对应哪条权威依据**，供后续演进时对照，避免拍脑袋偏离。

## 评审依据（已联网核实的来源）

| 来源 | 取到的要点 |
|---|---|
| Anthropic《Effective Context Engineering for AI Agents》 | 最小高信号 token；system prompt 的 "right altitude"；长任务三件套 **compaction（先最大召回再提精度）/ structured note-taking（外置记忆）/ multi-agent（子代理只回 1–2k 蒸馏摘要）**；context pollution |
| Anthropic《Claude Code Best Practices》 | 上下文是第一约束；给 agent 可运行的 verify（test/build/Stop hook/对抗复查 subagent）；CLAUDE.md 要短、领域知识进 skills；hooks 做「每次必做」；explore→plan→code→commit |
| 《12-Factor Agents》(HumanLayer) | #3 own your context window、#5 unify execution & business state、#6 launch/pause/resume、#9 compact errors、#10 small focused agents、#12 stateless reducer |
| **obra/Superpowers** | skill **自动触发**（progressive disclosure）；brainstorming→writing-plans→subagent-driven-development；**两阶段对抗复查（先 spec 合规、再代码质量）**；plan 含精确文件路径/验证步骤；用 **drill eval harness 测 skill 行为本身** |
| **gsd-core / Get-Shit-Done** | `/gsd-new-project` 定 scope → discuss → plan（spawn researchers，plan 先对需求验证）→ execute（独立 plan 并行成 wave，每任务一个原子 commit、干净上下文）；**`.out-of-scope/` 一等公民**、VERSIONING.md；「**复杂度在系统、不在工作流**」，反对 enterprise ceremony |
| 母本 pf-custom-service `docs/ai-harness/**` | engineering-guidelines 的**方案四原则 / 失败路径优先 / 多视角推演 / 异常归宿点 / YAGNI 6 个月触发**；带日期的结构化 memory；结构良好的 ADR |
| OpenAI Codex / agents.md / agentskills.io（v0.4–v0.6 联网核实） | `.agents/skills/` 是 Codex 原生仓库级 skills 约定（跟随 symlink）；**SKILL.md 是 26+ 平台的跨工具开放标准**；AGENTS.md 是 Linux Foundation/AAIF 中立标准 |

## 核心设计 ← 对应权威

| 设计 | 对应依据 |
|---|---|
| 人读 `docs/` vs 机器 `.harness/` 严格分层，`check` 强制 | 12-factor #5；context-eng 外置记忆 |
| 有界 phase + compact→archive→默认不读、靠 `recall` 检索 | context-eng（compaction + 最小高信号 token）；CC「aggressively manage context」 |
| `state.yml` = phase 机器 source of truth | 12-factor #12 stateless reducer、#5 |
| checkpoint/HANDOFF = 可暂停/恢复 | 12-factor #6 launch/pause/resume |
| 启动文件只做 router + 行数上限 | CC「CLAUDE.md 要短，否则规则被淹没」 |
| 语义化 compact（先召回再精度，非机械截断） | Anthropic compaction 原则 |
| skill 自动触发、两阶段对抗复查、self-contained plan | obra/Superpowers + CC |
| 项目级 numbered phases + backlog、out-of-scope 一等、VERSIONING | gsd-core |
| 工程基线四原则 / 失败路径优先 / 异常归宿点 / 结构化 memory / ADR | 母本 pf-custom-service |
| `.agents/skills/` 单一来源 + 各工具软链/复制 | Codex 原生约定 + agentskills.io 标准 |

## 取其精华、弃其糟泊

**取（精华）**：自动触发 skill；brainstorm→plan→execute 管线；subagent-per-task + 干净上下文；两阶段对抗复查；plan 自包含 + 验证步骤；out-of-scope 一等；versioning 纪律；「复杂度在系统、不在工作流」。

**弃（明确不抄）**：

- GSD/BMAD/Speckit 的 **enterprise ceremony**（story points、sprint 仪式、stakeholder sync）。
- Superpowers 的**过刚强约束**（强制 TDD + 删除测试前代码）——只作**可选** policy，不设默认强制。
- **框架膨胀**（SDK / 多语言 / 数千 commit 的维护负担）——保**单文件、零依赖、轻量**；新增能力一律「可选、可回退、不增加每次启动加载量」。

## 贯穿原则（任何新增都要守）

保持最大优点——**轻量、单文件、人读/机器分层、有界上下文**。所有新增能力一律：**可选、可回退、不增加每次启动的加载量**（context-eng 最小高信号 token；GSD 复杂度藏进系统、不外溢到工作流）。
