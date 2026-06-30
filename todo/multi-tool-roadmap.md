# 多工具适配路线图（版本化清单）

> **核心理念（2026-06 联网核实后修正）**：
> 1. **SKILL.md 已是跨工具开放标准**（[agentskills.io](https://agentskills.io/home)，26+ 平台原生支持同一份 SKILL.md 不用改）——
>    可移植的不只是 markdown 内容，**打包机制本身也已标准化**。
> 2. **`.agents/skills/` 正好是 OpenAI Codex 官方的仓库级 skills 扫描约定**
>    （[Codex 官方文档](https://developers.openai.com/codex/skills)：从 cwd 向上扫到 repo root 的 `.agents/skills/`，并跟随 symlink）。
>    所以把唯一来源放 `.agents/skills/` 等于**免费拿下 Codex**。
> 3. **Cursor 官方 docs 已确认同样原生扫描 `.agents/skills/`**（与 Codex 一致），跨工具问题进一步收敛为：Claude 需目录软链，Codex/Cursor 零成本。
>
> 红线（沿用 backlog）：单文件优先、零/少依赖、可选可回退、不增加每次启动加载量。
> 每版必须满足「明确可行 + 真实工具验证 + 兼容旧库（upgrade 幂等）」才算完成。

---

## 各工具 skills 发现路径矩阵（落地依据）

| 工具 | 项目级 skills 路径 | 跟随软链? | 从 `.agents/skills/` 接入方式 | 源 |
|---|---|---|---|---|
| **Codex** | `.agents/skills/`（**原生**，向上扫描）| ✅ 官方确认 | **零成本，本就是源** | developers.openai.com/codex/skills |
| **Claude Code** | `.claude/skills/` | ✅ | 目录级相对软链（v0.4 已做）| — |
| **Cursor** | `.agents/skills/` + `.cursor/skills/`（**原生**，向上扫描）| — | **零成本，本就是源** | cursor.com/docs/skills |
| **VS Code / Copilot** | 支持 agent skills | 待查 | 待查 | code.visualstudio.com agent-skills |

> 另：**AGENTS.md** 是 Linux Foundation/AAIF 中立标准（Codex/Cursor/Windsurf/Aider/Gemini/Zed/Jules 全原生读），
> 但它是「指令文件」不是「skill 包」；Codex **不跟随** AGENTS.md 内的 @-文件引用（靠目录扫描发现 skill）。

---

## 当前状态

- **v0.4（✅）**：`.agents/skills/ai-harness/` 唯一真实来源；`.claude/skills/ai-harness` 目录级相对软链；软链不可用回退副本 + `harness check` 提示；`harness migrate` 收敛遗留 `.claude` 真实目录。**附带红利**：该目录正是 Codex 原生约定，Codex 零成本即可发现。
- **v0.5（✅）**：D6（checkpoint 不污染 HANDOFF）/ B5（4 单测 + `evals/` runner 与 4 场景）/ B6（lessons 超阈值 warning）/ D5（项目级 `OUT-OF-SCOPE.md`）/ C4（`--with-commands` 生成 slash command 模板）。
- **v0.6（✅）**：AGENTS.md / CLAUDE.md ROUTER 增一行指明 skill 唯一来源位置。**措辞已修正**：Codex 是**原生扫描 `.agents/skills/`** 发现 skill，**不是**靠读这行；这行对人类读者是文档指针，启动加载量不增。
- **v0.7（✅）**：分发打包——`pyproject.toml` + console_scripts，核心移到单文件模块 `ai_harness.py`（保住单文件零依赖），暴露 `harness` / `ai-harness` 双命令。支持 `uv tool install` / `pipx install` / `uvx --from`（git 或本地路径）一行安装。**实测**：uvx 一行在空目录生成完整骨架、`uv tool install` 后裸 `harness` 命令全链路通过。
- **v0.8（✅）**：Cursor 适配——Cursor 与 Codex 一样**原生扫描 `.agents/skills/`**，无需 `.cursor/skills/` 副本。初版误用复制方案已撤销；`check` warning + `migrate --apply` 清理 v0.8 遗留副本。

---

## 版本清单

| 版本 | 主题 | 交付 & 验证口径 | 状态 |
|---|---|---|---|
| **v0.4** | `.agents` 唯一来源 + Claude 目录软链 | `init/upgrade` 产出软链；`check` 校验；`migrate` 收敛；单测全绿 | ✅ done |
| **v0.5** | 打磨/演进（D6/B5/B6/D5/C4） | 36 单测 + 4 evals 全绿；check 0/0 | ✅ done |
| **v0.6** | AGENTS.md 指明 skill 来源（+ 确认 Codex 原生支持）| ROUTER 引用 + 文档化「Codex 原生扫 `.agents/skills/`」事实 | ✅ done |
| **v0.7** | 分发打包（pyproject + console_scripts）| `uv tool install` / `pipx` / `uvx --from` 一行安装，`harness` 进 PATH；实测通过 | ✅ done |
| **v0.8** | Cursor 适配（原生 `.agents/skills/`）| 撤销复制方案；`check` 检测遗留副本；`migrate --apply` 清理；测试 + eval 更新 | ✅ done |
| **release** | 发布 PyPI + OSS 治理 | `uvx ai-harness` 免 --from；CHANGELOG（LICENSE/CI 已就绪） | 低 |

> **适配范围已收敛**：只做 **Claude / Codex / Cursor** 三个平台。Windsurf / Aider / Gemini / VS Code 等**暂不做**（理由 + 重审条件见 `docs/ai-harness/OUT-OF-SCOPE.md`）——需求出现时再单列版本。

> **Cursor 关键点**：`.mdc` 是 Cursor 的 **rules**（`.cursorrules` 已废弃，迁到 `.cursor/rules/*.mdc` 或 AGENTS.md），不是 skill 包。
> Cursor 读 **skill** 走 `.agents/skills/` 与 `.cursor/skills/`（官方 docs）；**无需复制**，与 Codex 共用 `.agents/skills/` 唯一来源即可。

---

## 设计约束（每版都要遵守）

1. **唯一来源**：可移植内容只存在于 `.agents/skills/` 一处；Claude 侧只允许软链指回源。
2. **软链按工具定**：Claude 用 `ensure_symlink`；Codex / Cursor 原生扫 `.agents/skills/`，零适配成本。
3. **可选可回退**：可选能力用 `--with-<feature>` 开关，默认 off；`upgrade` 不主动添加未声明的适配器。
4. **校验闭环**：每个 check 分支（断裂/退化/遗留副本）+ 测试覆盖 init / idempotent / migrate。
5. **失败回退**：Claude 软链不可用时回退为复制副本，`check` warning，不阻塞。

---

## 反模式（明确不做）

- 不做「自动检测装了哪些工具就启用哪些适配器」（隐式行为难调试，违背可选可回退）。
- 不做「统一抽象层覆盖所有工具」——直接维护 N 个轻薄适配器（YAGNI）。
- 不把打磨项与多工具适配混合发版——一版做一件，便于回滚。
- 不把 Cursor skill 误做成 `.mdc` rules——二者不是一回事。
