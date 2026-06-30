# Out of Scope（项目级）

项目级稳定的「明确不做」清单。与 `.harness/phases/current/PLAN.md` 的 phase 级 out-of-scope 分层：
项目级在这里，phase 级临时在 PLAN 里。

> 写入要求：**理由 + 触发重审条件**。没有重审条件的项不要写，否则会变成永久禁令。

## 不做的事

- **暂不适配 Claude / Codex / Cursor 以外的工具**（Windsurf、Aider、Gemini CLI、VS Code 等）。
  **理由**：现有三个平台已覆盖主要使用场景；每多一个适配器都要配套 check 分支 + 测试 + 维护，违背"克制、不膨胀"红线。
  **重审条件**：出现明确需求（用户点名某平台），或该平台 skill 发现机制与现有差异大到值得单列版本时。
- _示例_：不做 GUI / web 控制台。**理由**：核心是单文件 CLI + 文本约定。
  **重审条件**：若每周新加入用户 ≥ 5 人且 70% 反馈来自非命令行用户。

## 与其它文档的边界

- `DECISIONS.md`：记「决定怎么做」。
- `OUT-OF-SCOPE.md`：记「明确不做」+ 重审触发条件。
- `PLAN.md` 的 Out of Scope：仅对当前 phase 临时有效，结束即过期。
