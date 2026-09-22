# Phase 3 搜索编码

`MacroLearner` 直接构造 macro search Alloy 模型，再调用 bundled AlloyMax 1.0.3 的 `CompUtil` 和 `TranslateAlloyToKodkod`。宏路径不调用 `LTLLearner.learn()`，不先搜索原始 DAG 再压缩。

## 编译上下文与有限域

每个 task 创建一个 `MacroCompilationContext`。`ConstraintStateRegistry` 从当前命题的 literal states 出发，对允许的 unary 和 binary transitions 反复饱和。整个过程重用 plan 中的同一个 product automaton instance；状态编号确定，不生成全笛卡尔积。

`FiberCatalog` 只建立一次，复用 Phase 1 的 `FiberTable(Q,B,alphabet)`。catalog key 保留 `(qIn, semanticType, nonEmpty, qOut)` 全部字段，含 empty 和 nonempty identity；rep 是固定词序下的最短代表。当前未做额外 fiber pruning。

## Skeleton 与预算

实际 anchor slots 数为 `K=min(B,p+3b+2)`，virtual root 不占 slot。每个 slot 可以 inactive 或选择 literal/unary/binary label 和一个完整 q-state。protected slots 必须 active 且保留 label/identity。普通 unary slots 只有 incoming macro ports 大于 1 才允许 active。

预分配 `1+3K` 个 port slots：R 与每个 anchor 的 CHILD/LEFT/RIGHT，按 arity 激活。每个 active port 选择一个 active target 和一个 fiber。允许共享 target，允许同父的 LEFT/RIGHT 指向同一 target。非空 fiber 的展开内部节点是各端口私有的。

`graph=~src.target` 是 anchor 间关系；`no iden & ^graph` 排除环；`active=R.target.*graph` 确保全部可达。slot 索引不是拓扑序。唯一普通 slot 对称性破除是 active anonymous prefix；不限制 protected slot 与依赖顺序。

每个 active anchor 占一个 Unit，每个 active port 占 rep.length 个 Unit；所有 Carrier 的 Unit 集两两不交。Unit 总域恰有 B 个元素，因此硬界限和目标恰好是：

```text
expandedSize = |active anchors| + sum(rep.length over active ports)
             = |Carrier.cost| <= B
```

`minsome Carrier.cost` 最小化该精确大小。Unit 没有语法标签、子节点或语义 valuation，不是原 DAG 的节点。各计数域的最大基数由 B、port slots、old edge 数界定，Int bitwidth 使用带符号安全位宽；不用可能溢出的固定 4-bit 算术。

## 状态与真值

每个 fiber 固定 qi/qo；active port 满足 `fiber.qi=target.state`。anchor state 按 label 及子端口 qo 的完整自动机转移确定，R 的 qo 必须接受。

各 lasso 的 successor、future、succPow(k) 在 Kotlin 编译阶段精确生成。每个 active anchor 和 port 在所有样本位置都有 Boolean valuation。fiber 语义来自 SemanticType：先可选否定 target vector，然后 ID/F/G/FG/GF，再通过 succPow(k) 读取。future 包含当前位置与完整可达循环；prefix 不会在进入 loop 后重复。模型不按 representative 语法计算语义。

anchor 使用自身 unary/binary label 与子端口值计算语义；R 在所有正样本位置 0 为真、所有负样本位置 0 为假。

## 身份约束

- LEFT/RIGHT 的直接子节点相同，当且仅当两个 fiber 都为空且 target 相同。
- NoDAGReuse 数不同的真实 parent。每条非空 incoming fiber 提供一个不同的私有 parent；空 fiber 的 incoming ports 按 source anchor 去重。空 virtual-root port 没有真实 parent，不计入。literal-excluded 版本跳过 literal targets。
- named direct child 要求对应 port target 正确且 fiber 为空。
- named reachability 用 anchor graph 的严格传递闭包。
- protected root 要求 R target 是该 identity 且 fiber 为空。
- preserved old edges 是受保护 pair 集合与 empty-fiber skeleton relation 的交集，按 pair 计数。

## Repair 的精确字典序优化

初版直接使用 `maxsome kept`。独立差分测试发现，当 kept 的全部候选边均不可能存在时，bundled AlloyMax 1.0.3 会把常量 false 的 multiplicity expression 提前作为硬 false 处理。对应源码见 bundled JAR 的 `OSGI-OPT/src/kodkod/engine/fol2sat/FOL2BoolTranslator.java` 中 `visit(MultiplicityFormula)`；`MAXSOME` 只在结果是 BooleanFormula 时添加 soft 标记。

实现没有修改依赖。现在先做可行的 size 优化，再在 `[当前已保留数, oldEdges.size]` 上二分硬约束 `#kept >= m`。每次仍由同一个 AlloyMax 后端执行精确 size 优化；SAT 时提升下界到该 assignment 的实际 kept，UNSAT 时降低上界。收敛后保留数已最大，返回 assignment 在该保留数下大小也最小。若初始任务 UNSAT，直接返回 UNSAT。零旧边、零可保留边均有效。

这不是新 SAT/MaxSAT 求解器，也没有以浮点权重近似优先级；它是对有界 repair 目标的精确多次后端调用。`optimizationPasses` 记录实际次数。

## 解码与独立检查

```text
Alloy assignment -> MacroAssignment -> MacroDag
                 -> Phase 2 expandCanonical -> FormulaDag -> renderer
```

decoder 为 anchor 保留身份，为 representative 创建私有 witness ID。Phase 2 verifier 检查原始展开、canonical 展开、完整 fiber replay、q-state、anchor 身份、端口预算、重新分解后的 skeleton/fiber/最短代表一致性。

`FinalSolutionVerifier` 额外检查 B/b、模型大小等于展开大小、protected label、identity predicates、不同 old edge 数、模型 anchor q-state，以及所有样本所有位置的 anchor/edge valuations。生产侧 `ConcreteLassoEvaluator` 按具体语法用最小/最大不动点求 F/G，独立于 symbolic SemanticType 编码。测试还使用 Phase 2 test-only lasso oracle，以及完全不调用 macro/fiber 的 DAG 枚举器。

## Debug

`analysis.json` 包含模式、B/b/p/K、state/fiber/port/valuation 域大小、实际 anchor/edge/expanded/binary 数、目标、状态与优化次数。另有 `constraint_states.txt`、`fiber_catalog.txt`、`macro_model.als`、repair bound 模型、`macro_assignment.txt`、`reconstructed_formula.txt`、`verification.json`。域和模型排序确定；solver 可在多个等价最优解间选择不同 assignment。`timing.json` 单独记录后端时间，不作性能结论。
