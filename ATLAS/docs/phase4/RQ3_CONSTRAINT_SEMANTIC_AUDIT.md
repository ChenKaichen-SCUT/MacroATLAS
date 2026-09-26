# RQ3 / E4 matched 约束语义一致性审计

对全部 623 个冻结的 E4 matched 输入，逐题校验原始 `.trace` 与适配文件的差异、输入 SHA-256、Kotlin `TaskParser` 输出，以及 `RecognizedConstraintAnalyzer` 的实际分支和 plan。适配仅删除允许运算符列表中的 `U`；所有约束文本原样保留。逐题结果为 **623/623 `EXACT_MATCH`**，10 个实际 family 均为 `EXACT_MATCH`；485 题无自定义结构约束，138 题覆盖 9 种非空约束文本。详细依据和限制见[总报告](../../experiment_artifacts/2026-09-26/rq3-constraint-audit/REPORT.md)、[逐种约束审计表](../../experiment_artifacts/2026-09-26/rq3-constraint-audit/constraint_profiles.csv)与[逐题映射](../../experiment_artifacts/2026-09-26/rq3-constraint-audit/per_case.csv)。

最容易误读的是 Voting：真实文件只要求根为 `G`，其中 9 题另要求 `Neg` 的直接孩子为 Literal。**没有**禁止根的直接孩子含时序运算符，也没有禁止整个子树含时序运算符。另一个关键点是原 ATLAS 的 `childrenOf[n]` 定义为 `n.^(l+r)`，即所有严格后代；Weakening 模板及通用 CNF/DNF 文本中的相应限制必须按传递闭包解释。MacroATLAS 的模板 automaton 按此处理，边界测试已覆盖 `G(F(x0))` 与蕴含子树内嵌时序节点的情况。

Robot 的 `one sig` 命名身份可位于根子树之外，MacroATLAS 因此使用可选 protected slot；旧边保留数只计算根子树中命名节点间的**直接边**。空 fiber 对应直接连接，非空 fiber 在端点间插入一元节点，且共享边界和父节点数在编码与最终展开 DAG 验证时分别检查。总报告列出未使用的命名节点如何在原 ATLAS-B 模型的非根部分补齐，不改变根可达公式或 repair 目标。

该结论针对 **E4 实际 623 个 matched 输入的结构约束**。通用 CNF/DNF、通用 named direct/reachability/root 和通用固定模板分支没有出现在这批输入中，已在报告中单列代码核查，但不计入 E4 的覆盖率。`FinalSolutionVerifier` 重算展开公式相对于已识别 plan 的状态、身份与旧边数；它不会重新解释原始 Alloy 文本，也不会独立证明优化最优性。

复现：在仓库根目录运行 `python3 ATLAS/scripts/phase4/rq3_constraint_semantic_audit.py --output <新目录>`。脚本会从仓库中的原始 benchmark 重新生成并逐个校验 623 个 matched 输入，运行相关 Kotlin 测试，随后按约束文本完整 SHA 分组，调用真实 parser/analyzer。遇到未知文本、parser/analyzer 不一致或适配改动会报告 `UNRESOLVED`/`MISMATCH`，不会按 family 名称赋予通过状态。审计产物还包含全部 matched 输入和 623 条 parser/analyzer 原始输出，便于脱离本地 `generated/` 目录核查。
