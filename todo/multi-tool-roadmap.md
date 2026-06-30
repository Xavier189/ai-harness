# 多工具适配路线图（版本化清单）

> **核心理念（2026-06 联网核实后修正）**：
> 1. **SKILL.md 已是跨工具开放标准**（[agentskills.io](https://agentskills.io/home)，26+ 平台原生支持同一份 SKILL.md 不用改）——
>    可移植的不只是 markdown 内容，**打包机制本身也已标准化**。
> 2. **`.agents/skills/` 正好是 OpenAI Codex 官方的仓库级 skills 扫描约定**
>    （[Codex 官方文档](https://developers.openai.com/codex/skills)：从 cwd 向上扫到 repo root 的 `.agents/skills/`，并跟随 symlink）。
>    所以把唯一来源放 `.agents/skills/` 等于**免费拿下 Codex**。
> 3. 真正的跨工具问题收敛为：**各工具在哪个目录发现 skill + 是否跟随软链**。跟随软链就软链，不跟随就复制。
>
> 红线（沿用 backlog）：单文件优先、零/少依赖、可选可回退、不增加每次启动加载量。
> 每版必须满足「明确可行 + 真实工具验证 + 兼容旧库（upgrade 幂等）」才算完成。

---

## 各工具 skills 发现路径矩阵（落地依据）

| 工具 | 项目级 skills 路径 | 跟随软链? | 从 `.agents/skills/` 接入方式 | 源 |
|---|---|---|---|---|
| **Codex** | `.agents/skills/`（**原生**，向上扫描）| ✅ 官方确认 | **零成本，本就是源** | developers.openai.com/codex/skills |
| **Claude Code** | `.claude/skills/` | ✅ | 目录级相对软链（v0.4 已做）| — |
| **Cursor** | `.cursor/skills/`（仅项目级）| ❌ **不跟随** | **必须复制/生成** | forum.cursor.com bug 149693 |
| **VS Code / Copilot** | 支持 agent skills | 待查 | 待查 | code.visualstudio.com agent-skills |

> 另：**AGENTS.md** 是 Linux Foundation/AAIF 中立标准（Codex/Cursor/Windsurf/Aider/Gemini/Zed/Jules 全原生读），
> 但它是「指令文件」不是「skill 包」；Codex **不跟随** AGENTS.md 内的 @-文件引用（靠目录扫描发现 skill）。

---

## 当前状态

- **v0.4（✅）**：`.agents/skills/ai-harness/` 唯一真实来源；`.claude/skills/ai-harness` 目录级相对软链；软链不可用回退副本 + `harness check` 提示；`harness migrate` 收敛遗留 `.claude` 真实目录。**附带红利**：该目录正是 Codex 原生约定，Codex 零成本即可发现。
- **v0.5（✅）**：D6（checkpoint 不污染 HANDOFF）/ B5（4 单测 + `evals/` runner 与 4 场景）/ B6（lessons 超阈值 warning）/ D5（项目级 `OUT-OF-SCOPE.md`）/ C4（`--with-commands` 生成 slash command 模板）。
- **v0.6（✅）**：AGENTS.md / CLAUDE.md ROUTER 增一行指明 skill 唯一来源位置。**措辞已修正**：Codex 是**原生扫描 `.agents/skills/`** 发现 skill，**不是**靠读这行；这行对人类读者是文档指针，启动加载量不增。
- **v0.7（✅）**：分发打包——`pyproject.toml` + console_scripts，核心移到单文件模块 `ai_harness.py`（保住单文件零依赖），暴露 `harness` / `ai-harness` 双命令。支持 `uv tool install` / `pipx install` / `uvx --from`（git 或本地路径）一行安装。**实测**：uvx 一行在空目录生成完整骨架、`uv tool install` 后裸 `harness` 命令全链路通过。

---

## 版本清单

| 版本 | 主题 | 交付 & 验证口径 | 状态 |
|---|---|---|---|
| **v0.4** | `.agents` 唯一来源 + Claude 目录软链 | `init/upgrade` 产出软链；`check` 校验；`migrate` 收敛；单测全绿 | ✅ done |
| **v0.5** | 打磨/演进（D6/B5/B6/D5/C4） | 36 单测 + 4 evals 全绿；check 0/0 | ✅ done |
| **v0.6** | AGENTS.md 指明 skill 来源（+ 确认 Codex 原生支持）| ROUTER 引用 + 文档化「Codex 原生扫 `.agents/skills/`」事实 | ✅ done |
| **v0.7** | 分发打包（pyproject + console_scripts）| `uv tool install` / `pipx` / `uvx --from` 一行安装，`harness` 进 PATH；实测通过 | ✅ done |
| **v0.8** | **Cursor 适配（方案已修正）** | 新增 `--with-cursor`：**复制** `.agents/skills/ai-harness/` → `.cursor/skills/ai-harness/`（Cursor 不跟随软链，故只能复制）；`check` 检测副本与源不一致（陈旧）；幂等 + 测试 | 中 |
| **v0.9+** | Windsurf / Aider / Gemini / VS Code 按需 | 先查各自 skills 路径与软链支持，再决定软链 or 复制；各加 `--with-<tool>` + check + 测试；不强加 | 低 |
| **release** | 发布 PyPI + OSS 治理 | `uvx ai-harness` 免 --from；LICENSE / CI / CHANGELOG | 低 |

> **v0.8 关键修正**：原方案写「生成 `.cursor/rules/*.mdc`」是**错的**——`.mdc` 是 Cursor 的 **rules**（`.cursorrules` 已废弃，迁到 `.cursor/rules/*.mdc` 或 AGENTS.md），不是 skill 包。
> Cursor 读 **skill** 走 `.cursor/skills/`，且**不跟随软链**，所以用**复制 + 陈旧检测**，不是软链、不是 .mdc 转换。

---

## 设计约束（每版都要遵守）

1. **唯一来源**：可移植内容只存在于 `.agents/skills/` 一处；其它目录只允许「软链」或「由源复制/生成的产物」。复制产物必须可由 CLI 重新生成，且 `check` 能识别陈旧（副本与源不一致）。
2. **软链 or 复制按工具定**：跟随软链的工具（Claude/Codex）用 `ensure_symlink`；不跟随的（Cursor）用复制，并由 `check` 检测陈旧。
3. **可选可回退**：每个适配器一个 `--with-<tool>` 开关，默认 off；`upgrade` 不主动添加未声明的适配器。
4. **校验闭环**：每个适配器同时新增 `check` 分支（断裂/陈旧/退化）+ 至少 3 类测试（init 产出 / idempotent / migrate 遗留布局）。
5. **失败回退**：不支持软链的平台（未开开发者模式的 Windows）自动复制为副本，`check` warning，不阻塞。

---

## 反模式（明确不做）

- 不做「自动检测装了哪些工具就启用哪些适配器」（隐式行为难调试，违背可选可回退）。
- 不做「统一抽象层覆盖所有工具」——直接维护 N 个轻薄适配器（YAGNI）。
- 不把打磨项与多工具适配混合发版——一版做一件，便于回滚。
- 不把 Cursor skill 误做成 `.mdc` rules——二者不是一回事。
