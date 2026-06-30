# Harness Lessons

只保留长期有效的 lesson；一次性过程细节留在 `.harness/phases/archive/`，
不要堆到这里（防止 memory 变成无界启动文档）。

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
