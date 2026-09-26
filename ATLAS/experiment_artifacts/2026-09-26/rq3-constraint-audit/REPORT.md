# RQ3 / E4 matched 约束语义审计

逐题输入、适配、TaskParser 和 RecognizedConstraintAnalyzer 核对：**623/623**。
审计状态：{'EXACT_MATCH': 623}。实际自定义文本有 **9** 种；另有 485 题无自定义约束。

| 实际 family | 题数 | 审计状态 |
| --- | ---: | --- |
| 5to10Traces | 190 | EXACT_MATCH |
| baseTest | 42 | EXACT_MATCH |
| disjunctedExistence | 29 | EXACT_MATCH |
| equal | 42 | EXACT_MATCH |
| increasingNumVariables | 56 | EXACT_MATCH |
| moreDetailedTest | 126 | EXACT_MATCH |
| peterson | 30 | EXACT_MATCH |
| robot | 20 | EXACT_MATCH |
| voting_machine | 10 | EXACT_MATCH |
| weakening | 78 | EXACT_MATCH |

## 实际出现的约束形式

| 规范化文本标识 | 题数 | 来源文件 | 识别结果 | 状态 |
| --- | ---: | --- | --- | --- |
| `e3b0c442` 无自定义结构约束 | 485 | `ATLAS/experiment_artifacts/2026-09-26/rq3-constraint-audit/inputs/5to10Traces/0000.trace` | `none` | EXACT_MATCH |
| `1a473c55` Robot RR：4 条旧边 + NNF | 10 | `ATLAS/experiment_artifacts/2026-09-26/rq3-constraint-audit/inputs/robot/RRtrace/order.trace` | `OfficialRobotRR;Repair;NoDAGReuse;LeftNotEqualRight` | EXACT_MATCH |
| `21281860` Peterson：响应 + x6,x2 | 5 | `ATLAS/experiment_artifacts/2026-09-26/rq3-constraint-audit/inputs/peterson/constrained/liveness1.trace` | `OfficialPeterson;NoSharedLiteralBranches;RequiredProposition(x6);RequiredProposition(x2)` | EXACT_MATCH |
| `26a1c5cd` Voting：根 G + NNF | 9 | `ATLAS/experiment_artifacts/2026-09-26/rq3-constraint-audit/inputs/voting_machine/voting10.trace` | `OfficialVoting;NNF` | EXACT_MATCH |
| `2d9df7af` Peterson：响应 + x6 | 10 | `ATLAS/experiment_artifacts/2026-09-26/rq3-constraint-audit/inputs/peterson/base/liveness1.trace` | `OfficialPeterson;NoSharedLiteralBranches;RequiredProposition(x6)` | EXACT_MATCH |
| `3733f60a` Robot RA：5 条旧边 | 10 | `ATLAS/experiment_artifacts/2026-09-26/rq3-constraint-audit/inputs/robot/RAtrace/final21.trace` | `OfficialRobotRA;Repair;NoDAGReuse;LeftNotEqualRight` | EXACT_MATCH |
| `45efdf2a` Voting：仅根 G | 1 | `ATLAS/experiment_artifacts/2026-09-26/rq3-constraint-audit/inputs/voting_machine/voting2.trace` | `OfficialVoting` | EXACT_MATCH |
| `6793473a` Weakening antecedent 模板 | 39 | `ATLAS/experiment_artifacts/2026-09-26/rq3-constraint-audit/inputs/weakening/weaken_antecedent/weaken_antecedent_100_10_10.trace` | `OfficialWeakeningAntecedent` | EXACT_MATCH |
| `a20f604f` Weakening consequent 模板 | 39 | `ATLAS/experiment_artifacts/2026-09-26/rq3-constraint-audit/inputs/weakening/weaken_consequent/weaken_consequent_100_10_10.trace` | `OfficialWeakeningConsequent` | EXACT_MATCH |
| `d58a9f51` Peterson：安全 + x2,x8 | 15 | `ATLAS/experiment_artifacts/2026-09-26/rq3-constraint-audit/inputs/peterson/base/safety1.trace` | `OfficialPeterson;NoSharedLiteralBranches;RequiredProposition(x2);RequiredProposition(x8)` | EXACT_MATCH |

完整原文、规范化 token、语义、编码与 verifier 位置见 `constraint_profiles.csv`；
每题输入 SHA、文件路径及 analyzer 实测结果见 `per_case.csv`；真实 Kotlin parser/analyzer 的完整逐题输出另存 `parser_analyzer.jsonl`。原文另存 `constraint_texts/`。

Voting 的真实约束仅为 `root in G`，9 题另有生效的 NNF；
文件**没有**“直接孩子无时序运算符”或“整个子树无时序运算符”约束。
测试用 `G(F(x0))` 证实 Macro 接受时序后代，并用 `G(!(F(x0)))` 区分有无 NNF。

ATLAS 的 `childrenOf[n] = n.^(l+r)` 是全部严格后代；`childrenAndSelfOf[n] = n.*(l+r)` 包含自身。
Weakening 的 operator、NNF 局部规则和 CNF/DNF 禁止嵌套规则均须按相应量词范围解释。
Macro 模板状态的 `body`、`containsAnd/Or`、`noAndBelowOr/noOrBelowAnd` 与该传递语义对应。

Robot repair 的 `one sig` 名称允许不在根子树；Macro 用可选 protected slot 表示。
未使用的命名节点可在 ATLAS-B 的非根部分补齐：RR 的 F0/F1 指向 Literal，And0
可指向两个不同 Literal；RA 的 G0/Neg0/F0 可指向 Literal，And0 可指向两个
不同 Literal。它们不会改变根可达大小或旧边保留数；`DAGNode = experimentReach + Literal + named`
给这些节点保留了 scope。非空 fiber 只在命名节点之间插入匿名一元节点，
因此只有空 fiber 构成指定的直接旧边。
结构预算 `K=min(B,p+3b+2)` 只给 Literal、二元节点、受保护节点和共享一元节点留锚位；
其余一元链进入 fiber。根 G 无父节点，可从根 fiber 移到根锚，不改变可表示公式、
共享关系或大小；`MacroConstraintPlan.kt:56`、`AnchorExtractor.kt:9-40` 和
`MacroAlloyModelBuilder.kt:22-27,103-112` 给出这一路径。
NoDAGReuse 的 `lone n.~(l+r)` 计算不同父节点身份：两个空 port 来自同一父节点仍只算一个；
非空 fiber 的每个 port 会新建一元链头，因此可产生新的父节点。Macro 编码同时检查
非空 ingress 数、空 ingress 的不同 src 数与二者不共存；`no l & r` 则要求二元左右
展开后的直接孩子不是同一节点。最终 verifier 直接在展开 DAG 上复核父节点数与左右孩子身份。

FinalSolutionVerifier 重算的是已识别 plan 的自动机状态、身份约束和 repair 旧边计数，
**不重新解释原始 Alloy 约束文本，也不独立证明优化最优性**。文本到 plan 的等价性由本表、
完整块匹配和源码分支核对；E4 求解器结果一致本身不构成该证明。

## 重点核查的其余代码分支

| 条件 | 623 题中实际出现 | 语义与实现 |
| --- | --- | --- |
| NNF | Voting 9 题、Robot RR 10 题 | `Neg.l` 必须是**直接** Literal；`NnfAutomaton` 逐层传递无效状态，最终重新求根状态。 |
| RequiredProposition | Peterson 30 题 | 指定 xN 必须在根的包含自身的子树中；自动机 OR 传播出现位，最终重新求根状态。 |
| CNF/DNF | 0 题 | 原通用文本的 `childrenOf[n]` 是**全部严格后代**，不是直接孩子；CNF 禁 And 位于 Or 后代，DNF 对偶，均要求命题节点与直接原子否定。`CnfAutomaton`/`DnfAutomaton` 传播子树标志；此项仅作为通用代码审查，不计入 E4 结论。 |
| 通用 named direct/reach/root | 0 题 | 通用 analyzer 编译成 `NamedDirectChild`（指定 port 的空 fiber）、`NamedReachability`（锚图 `^graph` 严格后代）、`NamedRoot`（空 root fiber）；verifier 在展开 DAG 上分别检查直接孩子、图可达与根身份。Weakening 的特殊模板另以状态表示存在命名节点。 |
| 通用 G(Prop)、响应 template | 0 题 | `FixedTemplateAutomaton` 的通用分支未被 E4 采用；E4 的 Peterson 响应与 Weakening 模板走各自的完整块分支。 |
| NoDAGReuse / LeftNotEqualRight / repair | Robot 20 题 | 分别按非 Literal 的不同父节点、二元节点的直接左右孩子身份、指定旧边直接连接的保留数检查；上文给出编码与 verifier 对应关系。 |

通用分支源码在 `RecognizedConstraintAnalyzer.kt:215-249`、
`CnfAutomaton.kt`、`DnfAutomaton.kt` 和 `MacroAlloyModelBuilder.kt:158-170`；
通用分支的测试结果不冒充 E4 实际使用。

测试：{'ConstraintSemanticAuditTest': {'tests': 2, 'failures': 0, 'errors': 0, 'skipped': 0}, 'ConstraintAutomataTests': {'tests': 11, 'failures': 0, 'errors': 0, 'skipped': 0}, 'MacroSearchTest': {'tests': 9, 'failures': 0, 'errors': 0, 'skipped': 0}, 'MacroDifferentialTest': {'tests': 2, 'failures': 0, 'errors': 0, 'skipped': 0}}。
复现：从仓库根目录执行 `python3 ATLAS/scripts/phase4/rq3_constraint_semantic_audit.py --output <新目录>`；
脚本会先运行相关 Kotlin 测试并构建 classpath，再逐题调用真实 parser/analyzer。

**结论：这 623 个 E4 matched 案例实际使用的结构约束，已逐项核对为 EXACT_MATCH。**
