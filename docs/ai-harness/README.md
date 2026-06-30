# AI Harness

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
