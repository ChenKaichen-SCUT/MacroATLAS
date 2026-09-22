# 适用性与结果解释

- exact optimality 仅针对当前 U-free、可完整识别约束、给定 B/b 的候选域。
- 原样 artifact、U-free variant 和 synthetic 是不同工作负载，必须分表。
- ATLAS-B 的节点目标、固定 scope 与 trace successor 范围限制是公平比较适配，Original 的历史目标/递增 scope/trace 编码不受改变；二者必须分开命名。
- 只验证 SAT 的具体 witness；UNSAT 是后端结果，不声称拥有独立 UNSAT proof checker。
- 原始 raw Alloy 的 arbitrary structural constraints 仍依赖原后端；Original 额外检查 concrete trace truth，不能称作完整 Macro FinalSolutionVerifier。
- Alloy 只提供 total clauses；hard/soft split 未提供，不能据此报告拆分数字。
- 进程组 RSS 是 50ms 采样近似；不是 cgroup peak，RSS guard 也不是硬 memory limit。
- overhead component 不包含所有启动和 IO；总时间以外部 wall clock 为准。
- profile 配置对照会改变可行域，不等于禁用单组件的因果消融。
- 当前 WSL 硬件预检不足以形成正式论文性能结论；先在同一原生 Linux 服务器重跑双方。
