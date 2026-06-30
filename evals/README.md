# evals/

ai-harness 的**行为 eval**：用声明式 JSON 描述「初始状态 → 顺序命令 → 期望」，不依赖 unittest 框架，纯标准库可跑。

## 使用

```bash
python3 evals/run.py
```

退出码 0 = 全部通过；非零 = 有场景失败，打印第一处不匹配。

## 场景格式

`evals/scenarios/<name>.json`:

```json
{
  "setup": {
    "docs/ai-harness/current-status.md": "旧内容\n"
  },
  "steps": [
    ["migrate"],
    ["migrate", "--apply"]
  ],
  "expect": {
    "exit": 0,
    "file_absent": ["docs/ai-harness/current-status.md"],
    "file_contains": {"docs/ai-harness/STATE.md": "旧内容"},
    "stdout_contains": []
  }
}
```

支持的 expect 键：`exit`、`file_exists`、`file_absent`、`file_contains`、`file_not_contains`、`stdout_contains`。

## 与 unittest 的分工

- `tests/`：单测，覆盖代码分支与回归。
- `evals/`：场景级行为，描述端到端"用户做这一串操作应该得到什么"，更接近用户视角，便于新增"已修过的 bug 永不复发"清单。
