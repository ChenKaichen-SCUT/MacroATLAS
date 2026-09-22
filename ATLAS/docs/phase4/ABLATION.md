# 安全配置对照

不实现未经证明的“关闭 fiber 状态”或“忽略 identity”开关。保留 Phase 3 的 exact semantics。使用指引允许的安全替代方案：

- Original matched concrete DAG 编码；
- 无附加约束的 Macro；
- Macro + NNF / RequiredProposition；
- protected X-chain identity 参数系列（Full Macro）。

`synthetic.py` 的 `ablation/none`、`ablation/nnf`、`ablation/required` 使用相同 target、seed、B/b 和 trace 集。每个配置内部均与同域 ATLAS-B 比较，产生 model/vars/clauses、fiber count、分阶段时间及 solved。`p/` 系列观察 identity 对 kernel bound 和开销的影响。

不同约束配置会改变可行域，因此这是一组安全配置对照，不能解释为严格隔离单个组件的因果贡献。未实现 A1/no-quotient，以免更改冻结算法。结果图只由正式 raw data 自动产生，尚无性能结论。
