# Harness Policies

## Core Harness Policy

- `docs/` 用于人读 standard、policy、decision 和 design doc。
- `.harness/` 用于机器可读 state、active phase progress、archive 和生成的 check 输出。
- 启动文件只负责把 agent 路由到有界 context；它们不是 knowledge base。
- archive folder 默认不读取。
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
