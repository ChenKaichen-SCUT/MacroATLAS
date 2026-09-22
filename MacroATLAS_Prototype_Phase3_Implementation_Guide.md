# MacroATLAS Prototype 第三阶段代码实现指引
## 目标：让 MacroDAG 第一次进入真实搜索路径，实现可运行的 MacroATLAS 求解模式

> 本文件用于直接交给代码大模型。
>
> 起点是已经完成并验收的 Phase 1 与 Phase 2：
>
> - Phase 1：`UnaryNormalizer + ConstraintAutomata + FiberTable`
> - Phase 2：真实 `LTLLearningSolution -> FormulaDag -> MacroDag -> canonical FormulaDag` 的压缩—重建正确性闭环
>
> Phase 3 的任务不再是“对 ATLAS 已经求出来的公式做后处理”，而是：
>
> **直接在 MacroDAG / anchor / fiber 空间中搜索候选公式，并把求得的 MacroDAG 重建成普通 LTL formula。**
>
> 当前阶段仍然不做正式性能实验、cactus plot、论文 speedup claim。完成 Phase 3 后，再单独设计和执行实验。

---

# 0. Phase 3 的一句话目标

实现一个 opt-in 的：

```text
MacroATLAS solver path
```

使数据流变成：

```text
.trace / ATLAS input
        |
        v
recognized constraint + objective analysis
        |
        +---- unsupported ----> original ATLAS fallback
        |
        v
MacroSearchConfig
        |
        v
finite constraint states + FiberTable
        |
        v
O(b+p)-budgeted MacroDAG search model
        |
        v
trace semantics over macro edges
        |
        v
AlloyMax / OpenWBO solving
        |
        v
MacroDag assignment
        |
        v
Phase 2 MacroDagExpander
        |
        v
ordinary FormulaDag / LTL string
        |
        v
independent correctness verification
```

Phase 3 完成后，应该第一次能够运行类似：

```bash
java ... --macro=force ...
```

并让 solver **直接搜索 macro representation**，而不是先由原 ATLAS 求普通 DAG 再压缩。

---

# 1. 不要从 0 重写求解器

必须继续在已经完成 Phase 2 的当前 ATLAS 分支上开发。

不要创建：

```text
macroatlas-new/
```

重新写 parser、trace model、AlloyMax wrapper 或 CLI。

必须优先复用：

- ATLAS 已有 trace/input parser；
- proposition 与 trace representation；
- Alloy / AlloyMax / OpenWBO 接口；
- Phase 1 `UnaryNormalizer`；
- Phase 1 `ConstraintAutomaton`；
- Phase 1 `FiberTable`；
- Phase 2 `FormulaDag`；
- Phase 2 `MacroDag`；
- Phase 2 `MacroDagExpander`；
- Phase 2 independent lasso semantics oracle；
- Phase 2 verifier / statistics。

Phase 3 的本质是：

```text
新增一个 Macro search encoding
```

而不是：

```text
重新实现 ATLAS
```

---

# 2. 开始前必须核对当前代码状态

代码大模型首先运行：

```bash
git status --short
git log -5 --oneline --decorate
mvn -B clean verify
```

并阅读：

```text
docs/phase1/
docs/phase2/
```

特别是：

```text
docs/phase2/IMPLEMENTATION_REPORT.md
docs/phase2/validation/TEST_RESULTS.md
```

如果 Phase 2 的实际类名、package、接口与上一份设计指引略有差异：

> 以已经验收通过的实际 Phase 2 API 为准。

不要为了让代码“长得像本文件”而重写已经正确的 Phase 2。

在 Phase 3 开始前记录：

```text
PHASE2_BASE_COMMIT=<commit>
```

最终报告中必须给出该 commit。

---

# 3. 当前阶段的理论保证范围

Phase 3 第一版只为下面的 fragment 提供 Macro 求解路径。

## 3.1 LTL fragment

允许：

```text
literals
!
X
F
G
&
|
->
```

具体 operator 名称必须映射到 ATLAS 当前实际 enum / representation。

不支持 macro-normalization：

```text
U
```

如果输入、候选 operator set 或 recognized template 要求 binary temporal `U`：

```text
AUTO mode -> fallback original ATLAS
FORCE mode -> structured Unsupported error
```

不能静默删除 `U`。

---

## 3.2 Constraint fragment

Macro path 只允许：

### A. compositional constraints

能够由 Phase 1 / Phase 3 的 finite bottom-up `ConstraintAutomaton` 完整观察，例如：

- propositional-only subtree；
- NNF；
- CNF；
- DNF；
- required proposition；
- fixed liveness/template constraints；
- invariant-weakening 中可编译为有限状态的部分；
- 它们的 product。

### B. macro-skeleton identity constraints

只依赖：

- protected node identity；
- macro source / target；
- port `ROOT/CHILD/LEFT/RIGHT`；
- direct edge (`fiber.nonEmpty == false`)；
- distinct parent / sharing；
- `left == right` / `left != right`；
- protected-node reachability；
- fixed oldSpec protected edges。

这些不进入 unary fiber state，而在 MacroDAG search model 上直接编码。

### C. 支持的 optimization objectives

Phase 3 第一版只支持：

1. minimum expanded formula size；
2. repair：
   - first maximize preserved `oldSpec` edges；
   - then minimize expanded formula size。

其他 arbitrary AlloyMax objectives：

```text
AUTO -> fallback
FORCE -> Unsupported
```

---

# 4. Phase 3 明确不做什么

当前阶段不要：

1. 宣称支持任意 raw Alloy constraint；
2. 实现完整 Alloy parser / theorem prover；
3. 实现 generic rank-2/rank-3 FO-type automaton；
4. 支持 binary temporal `U` 的 macro quotient；
5. 替换 OpenWBO / AlloyMax；
6. 写新的 SAT/MaxSAT solver；
7. 做完整论文 benchmark；
8. 画 speedup/cactus plot；
9. 对性能作正式 claim；
10. 删除 original ATLAS fallback；
11. 改变原 ATLAS 默认 CLI 行为；
12. 为了“更快”牺牲 exact optimality。

当前阶段首先追求：

```text
search correctness
+
safe applicability detection
+
exact reconstruction
+
baseline compatibility
```

---

# 5. 新增的核心概念：MacroConstraintPlan

Phase 2 的 `MacroEligibility` 只负责已经给定：

```text
FormulaDag
ConstraintAutomaton
protected IDs
allowed unary operators
```

时判断一个**已经存在的 DAG**是否可以压缩。

Phase 3 要在公式还没有生成前做搜索，因此需要一个新的、面向输入任务的计划对象。

建议新增：

```kotlin
data class MacroConstraintPlan<Q : Any>(
    val automaton: FiniteConstraintAutomaton<Q>,
    val protectedIdentities: List<ProtectedIdentity>,
    val identityConstraints: List<MacroIdentityConstraint>,
    val objective: MacroObjective,
    val allowedUnaryOperators: Set<UnaryOperator>,
    val allowedBinaryOperators: Set<BinaryOperator>,
    val propositions: List<String>,
    val nodeBudget: Int,
    val binaryBudget: Int
)
```

实际字段可按当前代码风格调整。

关键点：

> `MacroConstraintPlan` 是“Macro compiler 已经理解并证明安全的约束表示”。

不要把 raw Alloy string 直接塞进 Macro search builder 并假装已经支持。

---

# 6. FiniteConstraintAutomaton：Phase 3 需要显式状态域

Phase 1 的 `ConstraintAutomaton<S>` 可以只做 transition，不一定暴露全部 state。

但 Macro search encoding 必须让 solver 选择 / 约束：

```text
q_v
qIn_e
qOut_e
```

所以 Phase 3 需要**有限可枚举状态域**。

优先检查 Phase 1 当前实现。

如果已经存在 state enumeration API，直接复用。

否则做最小向后兼容扩展，例如：

```kotlin
interface FiniteConstraintAutomaton<S : Any> : ConstraintAutomaton<S> {
    fun states(): List<S>
}
```

或者：

```text
ConstraintStateDomain<S>
```

独立于原 interface。

要求：

1. `states()` deterministic；
2. 无重复；
3. 包含所有 transition 可能返回的 state；
4. product automaton 也能 lazy/saturated 地枚举所有 reachable states；
5. 不修改 Phase 1 已验证 transition 的数学含义。

---

# 7. Product automaton 的状态域生成

不要简单写：

```text
Q1 x Q2 x ... x Qk
```

并全部预生成。

应当实现 reachable-state saturation：

```text
seed literal states
        |
        v
apply all allowed unary transitions
        |
        v
apply all allowed binary transitions
        |
        v
repeat until fixed point
```

如果 proposition-specific automaton（例如 RequiredProp）依赖 proposition 名字，应对当前输入的 proposition set 生成 literal states。

建议实现：

```kotlin
ConstraintStateRegistry<Q>
```

提供：

```text
states
stateId(q)
literalTransition
unaryTransition
binaryTransition
```

最终 Macro search encoding 只操作整数 state IDs，而不是把复杂 Kotlin object 写进 model。

---

# 8. RecognizedConstraintAnalyzer

Phase 3 必须采用：

```text
fail closed
```

策略。

新增：

```text
RecognizedConstraintAnalyzer
```

输入应优先使用 ATLAS 已经 parse 后的 representation。

如果原 ATLAS 对 custom constraint 只保留 raw Alloy text，则：

1. 先检查是否已经有 Alloy AST / parser object 可复用；
2. 若没有，不要在 Phase 3 写完整 Alloy parser；
3. 只对已知 canonical benchmark/template 形式做严格 recognition；
4. 无法确认语义完全匹配时返回 unsupported。

禁止：

```text
contains("NNF")
contains("oldSpec")
```

这种脆弱启发式 recognition。

---

# 9. Constraint analysis 的输出

建议：

```kotlin
sealed class MacroTaskAnalysis {
    data class Supported(
        val plan: MacroConstraintPlan<*>,
        val recognizedFeatures: List<RecognizedFeature>
    ) : MacroTaskAnalysis()

    data class Unsupported(
        val reasons: List<MacroUnsupportedReason>
    ) : MacroTaskAnalysis()
}
```

原因必须结构化，例如：

```text
BINARY_TEMPORAL_UNTIL_REQUIRED
UNKNOWN_CUSTOM_ALLOY_CONSTRAINT
UNSUPPORTED_OBJECTIVE
UNSUPPORTED_IDENTITY_PREDICATE
UNRECOGNIZED_TEMPLATE
PROTECTED_IDENTITY_NOT_RESOLVABLE
BINARY_BUDGET_MISSING
```

不要只返回 `"unsupported"`。

---

# 10. Phase 3 第一版应识别哪些任务

不要一开始追求覆盖所有 ATLAS input。

按优先级实现。

## Tier 0：无 custom structural constraint

最简单的普通 constrained-by-traces learning：

```text
positive / negative traces
minimum size
U-free
binary budget b
```

这必须最先跑通。

## Tier 1：Phase 1 已有直接 automaton

至少：

- PropositionalOnly；
- NNF；
- CNF；
- DNF；
- RequiredProposition；
- 它们的 Product。

## Tier 2：ATLAS 论文中的 fixed template

建议实现专门 automata，而不是在 solver 中散落模板逻辑：

```text
G(Prop)
G(Prop -> F Prop)
```

如果 Phase 2/Phase 1 已经有相应 automaton，直接复用。

否则新增：

```text
LivenessTemplateAutomaton
```

必须有独立 tests。

## Tier 3：identity constraints

至少：

```text
NoDAGReuse
LeftNotEqualRight
NamedDirectChild
NamedReachability
```

这些不进入 automaton，进入：

```text
MacroIdentityConstraint
```

## Tier 4：repair

识别：

```text
protected old nodes
oldSpec fixed edge set
maximize kept old edges
then minimize expanded size
```

这要求 protected identities 在 macro search slots 中显式保留。

## Tier 5：invariant weakening

只有在代码模型能明确映射 ATLAS benchmark 的实际 constraints 时实现。

建议建立一个整体：

```text
InvariantWeakeningAutomaton
```

而不是让 CNF/DNF/template 条件散落在 MacroAlloy generator 中。

如果输入形式不能安全识别：

```text
fallback
```

不要为了“覆盖 benchmark”使用错误识别。

---

# 11. MacroSolverMode

新增 opt-in 模式。

推荐：

```text
OFF
AUTO
FORCE
```

含义：

## OFF

完全运行 original ATLAS。

这是默认值。

必须保证：

```text
没有 --macro 参数时行为与 Phase 2 完全一致。
```

## AUTO

先做 `RecognizedConstraintAnalyzer`。

若 Supported：

```text
Macro solver
```

若 Unsupported：

```text
记录 fallback 原因
-> original ATLAS
```

## FORCE

Supported：

```text
Macro solver
```

Unsupported：

```text
直接报结构化错误
```

**FORCE 不允许静默 fallback。**

---

# 12. Binary budget 的语义必须明确

理论 Macro-Kernel 假设：

\[
\#BinaryNodes \le b.
\]

因此 Phase 3 第一版必须把 `binaryBudget` 作为显式求解参数。

例如：

```bash
--macro-max-binary 3
```

不要默认为一个很小的数字却仍宣称与 unrestricted ATLAS 完全等价。

正确语义：

> MacroATLAS 在给定 `nodeBudget B` 和 `binaryBudget b` 的 fragment 内求 exact optimum。

如果需要与 unrestricted original ATLAS 完全同域：

```text
b >= B
```

是安全但可能失去 kernel 优势的保守选择。

Phase 3 不需要现在发明“什么时候可以提前停止 incremental b”的新理论。

---

# 13. Search anchor-slot budget

给定：

```text
B = nodeBudget
b = binaryBudget
p = protected identity count
```

理论上 structural anchors 至多：

\[
p+3b+2.
\]

实际任何公式也不可能超过 `B` 个 actual nodes。

因此搜索 slot 上限使用：

\[
\boxed{
K = \min(B,\ p+3b+2)
}
\]

`VirtualRoot` 不算 actual anchor slot。

---

# 14. Anchor slot 类型

每个 slot 至少有：

```text
active
kind
label/operator/proposition
protectedIdentity?
constraintState
topologicalRank / acyclicity information
```

`kind`：

```text
LITERAL
UNARY_ANCHOR
BINARY
```

搜索中仍允许 `UNARY_ANCHOR`，因为：

- protected unary node 必须显式存在；
- shared unary node 必须显式存在；
- 它们不能被吞入 private macro edge。

普通非共享、非 protected unary nodes不作为 anchors，由 fiber edge 表示。

---

# 15. Protected slots

对每个 protected identity必须在 slot model 中有唯一对应。

建议：

1. 预留 protected slots；
2. protected slot 永远 active；
3. protected label若输入已经确定，则固定；
4. protected IDs不与 anonymous slots混淆；
5. anonymous slot永远不能冒充 protected ID。

如果 protected identity 自己是否允许从 final formula 删除在 Phase 2 中已有明确 policy，则严格复用该 policy。

---

# 16. Anonymous slots 的基本约束

至少：

```text
active prefix symmetry breaking
```

例如：

```text
anonSlot[i+1].active -> anonSlot[i].active
```

每个 active slot：

- 恰选一种 kind；
- kind 决定合法 label；
- inactive slot不得被 target；
- literal无 outgoing ports；
- unary anchor有 CHILD；
- binary有 LEFT / RIGHT。

不要强制不同 anonymous slots label不同。

---

# 17. Macro port model

完全复用 Phase 2：

```text
VirtualRoot.ROOT
UnaryAnchor.CHILD
Binary.LEFT
Binary.RIGHT
```

每个 active port恰选择：

```text
target anchor slot
fiber ID
```

literal slot没有 port。

VirtualRoot ROOT永远存在且恰有一个 assignment。

---

# 18. Sharing 的表示

多个 ports可以选择相同 target anchor。

如果 edge nonempty：

```text
source -> fresh private unary chain -> target
```

不同 macro edges的 fresh chain互相不同。

这些 fresh nodes不需要 solver-level physical identity。

---

# 19. Acyclicity

Macro skeleton必须是 DAG。

不要直接把 slot index当拓扑序，除非能证明 protected slots不破坏 completeness。

推荐：

```text
rank[v] in 0 .. K-1
```

每个 active edge：

```text
rank[source] < rank[target]
```

VirtualRoot视为 rank = -1。

---

# 20. Root reachability

不能只保证 acyclic。

必须禁止：

```text
active but disconnected anchors
```

最安全方式是显式 reachability variables：

```text
Reach[v]
```

或：

```text
ReachStep[d][v]
```

从 VirtualRoot target向下传播。

只有 reachable slot允许 active，或反过来要求：

```text
active -> reachable
```

---

# 21. Binary-node budget

hard constraint：

```text
sum(active[v] && kind[v] == BINARY) <= b
```

---

# 22. Fiber domain 的建立

对当前 task：

```text
FiniteConstraintAutomaton<Q>
allowed unary operators
nodeBudget B
```

先建立：

```text
ConstraintStateRegistry<Q>
```

再使用 Phase 1 `FiberTable` 对所有 qIn states建立 catalog。

每个 entry记录：

```text
id
qIn
qOut
semanticType
nonEmpty
representativeWord
representativeLength
```

---

# 23. Empty fiber

必须存在：

```text
empty word
semantic = identity
nonEmpty = false
qOut = qIn
length = 0
```

它不能与 `!!` 等 nonempty identity-semantic word合并。

---

# 24. Anchor constraint state

每个 active anchor slot有：

```text
q[v] in Q
```

Literal：

```text
q[v] = literalState(p)
```

Unary anchor：

```text
q[v] = unaryState(op, childEdge.qOut)
```

Binary：

```text
q[v] = binaryState(op, leftEdge.qOut, rightEdge.qOut)
```

---

# 25. Macro edge 的 qIn / qOut 一致性

若：

```text
source.port --fiber f--> target t
```

必须：

```text
f.qIn == q[t]
```

`f.qOut` 成为 source 对该 child port 看见的 state。

---

# 26. Root constraint state

VirtualRoot ROOT edge：

```text
ROOT --fiber f--> target
```

whole formula root state：

```text
f.qOut
```

正常 recognized hard constraints要求：

```text
f.qOut is accepting
```

---

# 27. Expanded formula size

真实 reconstructed DAG node count：

\[
\boxed{
Size =
\#activeAnchors
+
\sum_{activeMacroEdges e} len(fiber(e))
}
\]

VirtualRoot不计。

hard bound：

```text
expandedSize <= B
```

minimum-size objective：

```text
minimize expandedSize
```

---

# 28. Phase 3 semantic encoding 原则

Macro anchors：

```text
有 identity
参与 L/R/sharing/oldSpec
```

Fiber interior：

```text
无 identity
只参与 trace semantics
```

不要为了 trace semantics把 fiber重新变成一般 DAG search nodes。

---

# 29. SemanticType 的直接 lasso 语义

fiber semantic type：

\[
X^k\tau\neg^\epsilon
\]

其中：

```text
tau = ID, F, G, FG, GF
```

生产 semantic encoding直接使用 `SemanticType`。

代表 word只用于 reconstruction。

---

# 30. Lasso position helper

对每条 trace预计算：

```text
succ[i]
succPow[k][i]
future[i]
```

ultimately periodic semantics必须精确，不使用 finite horizon approximation。

---

# 31. Edge semantic value

对每个 macro edge和 trace position：

```text
edgeVal[e][i]
```

设 target anchor value为 `childVal`。

先 optional negation，再 tail，再最外层 `X^k`。

例如：

```text
(k=2, tail=FG, neg=true)
```

表示：

\[
X^2F(G(\neg child)).
\]

---

# 32. Tail 精确语义

设 `base` 为 optional NOT 后 child value。

ID：

```text
tailVal[i] = base[i]
```

F：

```text
OR(base[j] for j in future[i])
```

G：

```text
AND(base[j] for j in future[i])
```

FG：

```text
g[i] = AND(base[j] for j in future[i])
tailVal[i] = OR(g[j] for j in future[i])
```

GF：

```text
f[i] = OR(base[j] for j in future[i])
tailVal[i] = AND(f[j] for j in future[i])
```

最后：

```text
edgeVal[i] = tailVal[succPow[k][i]]
```

---

# 33. 不要依赖 Phase 2 test oracle 作为生产编码

Phase 2 independent evaluator只作为测试 oracle。

生产 path应使用 AlloyMax / symbolic constraints。

测试必须对比：

```text
production macro semantics
vs
Phase 2 independent evaluator
```

---

# 34. Anchor semantic value

Literal：

```text
trace proposition valuation
```

Unary anchor：

```text
apply !/X/F/G to CHILD edge value
```

Binary：

```text
apply &/|/-> to LEFT/RIGHT edge values
```

当前 macro path不允许 U。

---

# 35. Whole-formula value

VirtualRoot ROOT edge输出：

```text
formulaVal[t,i]
```

positive：

```text
formulaVal[t,0] = true
```

negative：

```text
formulaVal[t,0] = false
```

---

# 36. AlloyMax integration 策略

先检查当前 ATLAS 源码究竟是：

```text
生成 Alloy source
```

还是程序化构造模型。

沿用同一风格。

可以新增：

```text
MacroAlloyModelBuilder
MacroSearchEncoding
MacroLearningSolver
```

但不要另换 solver backend。

---

# 37. Encoding 与 decoding 分层

搜索前：

```text
MacroSearchEncoding -> solver model
```

求解后：

```text
MacroAssignmentDecoder -> MacroDag
MacroDagExpander -> FormulaDag
```

不要把三个职责写进一个巨型 class。

---

# 38. MacroAssignmentDecoder

至少恢复：

```text
active anchors
anchor kind/label
protected identity
each port target
each port FiberId
constraint state IDs
```

然后构造 Phase 2 已有 `MacroDag`。

必须再次运行 Phase 2 validator / verifier。

---

# 39. FinalSolutionVerifier

solve 后至少检查：

1. FormulaDag structurally valid；
2. node count <= B；
3. binary count <= b；
4. no U；
5. recognized automaton root accepting；
6. protected identity constraints；
7. NoDAGReuse / child inequality 等；
8. positive traces satisfied；
9. negative traces rejected；
10. objective value与 assignment一致；
11. repair kept-edge count一致；
12. 再次 macro-extract 后 skeleton/fiber 与 assignment一致。

如果 Supported task进入 Macro solver后 verifier失败：

```text
fail loudly
```

不要 fallback掩盖 bug。

---

# 40. LeftNotEqualRight

对 binary anchor：

immediate children相等当且仅当：

```text
left fiber empty
AND
right fiber empty
AND
left target == right target
```

所以 `left != right` 必须按这一条件编码。

不能只写：

```text
leftTarget != rightTarget
```

---

# 41. NoDAGReuse

internal private unary nodes天然只有一个 parent。

只检查 anchors。

对 target anchor v：

```text
distinctParentCount(v)
=
#nonempty incoming macro edges
+
#distinct source anchors with empty edge to v
```

如果同一 binary source的 LEFT / RIGHT都 empty到 v：

distinct parent仍只算一个 source。

按原 ATLAS constraint是否排除 AP anchors分别处理。

---

# 42. Protected direct child

例如：

```text
left(a) == b
```

等价于：

```text
LEFT target == b
AND LEFT fiber empty
```

nonempty时 b只是 descendant。

---

# 43. Protected reachability

如果：

```text
b in desc(a)
```

则只需 macro skeleton directed reachability：

```text
a ~> b
```

因为每条 macro edge展开为有向 path。

---

# 44. Repair oldSpec objective

对 old edge `(a,b)`建立单一：

```text
keep[a,b]
```

当且仅当 a 的某个合法 port：

```text
target == b
AND fiber empty
```

如果 LEFT/RIGHT都 direct 到同一 b：

old edge只计一次。

objective：

```text
1. maximize sum keep[a,b]
2. minimize expandedSize
```

---

# 45. Objective abstraction

建议：

```kotlin
sealed class MacroObjective {
    class MinExpandedSize : MacroObjective()
    data class Repair(val oldEdges: Set<ProtectedEdge>) : MacroObjective()
}
```

语法按当前 Kotlin 1.7兼容方式调整。

---

# 46. Safe symmetry breaking

允许：

```text
anonymous active slots form prefix
```

其他 symmetry breaking必须明确证明 completeness保持。

宁可第一版 model稍大，不要用未经证明的 heuristic symmetry breaking。

---

# 47. 不要固定 slot index 为 topo order

protected slots若预留固定 index，直接：

```text
sourceIndex < targetIndex
```

可能破坏 completeness。

使用独立 topo rank更安全。

---

# 48. 不要让 representative syntax 成为生产 semantic source

建议严格：

```text
SemanticType -> trace semantics
representativeWord -> reconstruction
```

避免两个 semantic实现分叉。

---

# 49. ConstraintStateRegistry 与 FiberCatalog cache

同一个 task只构造一次：

```text
state registry
fiber catalog
lasso precomputation
```

建议集中到：

```text
MacroCompilationContext
```

---

# 50. FiberCatalog

建议 solver-friendly entry：

```kotlin
data class FiberCatalogEntry(
    val id: Int,
    val qInId: Int,
    val qOutId: Int,
    val semanticType: SemanticType,
    val nonEmpty: Boolean,
    val representativeWord: UnaryWord,
    val representativeLength: Int
)
```

IDs必须 deterministic。

---

# 51. Fiber domain pruning

target q已知/被变量选择时，只允许：

```text
fiber.qIn == target.q
```

的 catalog entries。

不要创建无意义笛卡尔积。

---

# 52. Formula-node bound

第一版只需精确 hard constraint：

```text
active anchors
+
sum fiber lengths
<= B
```

不需要做复杂下界传播。

---

# 53. Recognized no-constraint path 的最低可运行目标

必须先跑通：

```text
U-free
no custom structural constraint
minimum size
explicit b
```

再加入 templates / repair。

---

# 54. 建议 milestone

## M1

Finite state registry + FiberCatalog。

## M2

MacroSearchConfig / anchor slots / ports 的纯内存模型。

## M3

Structural Alloy encoding：

- acyclic
- reachable
- arity-correct
- B/b
- q consistency

## M4

Trace semantics。

## M5

Minimum expanded size objective。

## M6

Recognized compositional constraints。

## M7

Identity constraints。

## M8

Repair objective。

## M9

OFF/AUTO/FORCE/fallback CLI。

必须按顺序逐层验收。

---

# 55. M1 tests

对 NNF/CNF/DNF/RequiredProp/Product：

- finite；
- deterministic；
- transition closure；
- state IDs stable。

FiberCatalog重复构建必须完全相同。

---

# 56. M2 tests

例如：

```text
B=5,b=1,p=0 -> K=5
B=8,b=1,p=2 -> K=7
```

检查：

- virtual root不占 K；
- protected slots unique；
- literal/unary/binary port domain正确。

---

# 57. M3 structural model tests

对：

```text
B<=4
b<=1
```

小 model求解。

每个 decoded MacroDag：

```text
expandCanonical
FormulaDagValidator
MacroRoundTripVerifier
```

全部通过。

---

# 58. M4 semantic differential test

每个 Macro solver solution：

1. decode；
2. expand；
3. Phase 2 independent lasso evaluator；
4. 检查 trace classification。

随机手工 MacroDag还应逐 position对比生产 semantic encoding。

---

# 59. M5 objective correctness

极小：

```text
B<=5
b<=1
AP<=2
```

与 reference枚举比较最小 expanded size。

如果 original ATLAS难以施加同一 b bound，写测试侧 TinyReferenceEnumerator。

---

# 60. TinyReferenceEnumerator

仅放 `src/test/`。

枚举：

```text
U-free
small B
binary count <= b
```

用 Phase 2 lasso oracle检查。

用途：

```text
发现 Macro search漏解/假解
```

不是产品 solver。

---

# 61. M6 compositional differential tests

至少：

```text
NNF
CNF
DNF
RequiredProp
Liveness template
```

比较：

```text
SAT/UNSAT
OPT size
automaton acceptance
```

---

# 62. M7 identity tests

必须覆盖：

- same target + empty/empty => immediate child same；
- same target + nonempty/nonempty => immediate fresh child different；
- multiple ports share target；
- NoDAGReuse；
- protected direct child；
- protected reachability。

---

# 63. M8 repair tests

构造：

```text
candidate 1: keep 2, size 6
candidate 2: keep 1, size 4
candidate 3: keep 2, size 5
```

必须选 candidate 3。

LEFT/RIGHT都 direct同一 old edge时只计一次。

---

# 64. M9 CLI tests

OFF：

```text
original
```

AUTO supported：

```text
solverMode=MACRO
```

AUTO U/unknown constraint：

```text
fallback original
```

FORCE unsupported：

```text
error
```

FORCE绝不 fallback。

---

# 65. Result metadata

每次 Macro solve记录：

```text
solverMode
fallbackReason?
nodeBudget
binaryBudget
protectedCount
anchorSlotBudget
constraintStateCount
fiberCount
activeAnchorCount
activeMacroEdgeCount
expandedNodeCount
binaryNodeCount
objectiveValue
solverStatus
```

后续实验直接使用。

---

# 66. 计时 instrumentation

允许记录：

```text
analysisTime
fiberBuildTime
encodingBuildTime
solverTime
decodeTime
verifyTime
totalTime
```

当前仅用于 debug，不作 speedup claim。

---

# 67. Encoding-size instrumentation

若 AlloyMax API容易获取：

```text
boolean variables
hard clauses
soft clauses
```

则记录。

若不容易，不要现在重写 backend。

至少记录：

```text
K
port count
fiber count
q-state count
semantic valuation count
```

---

# 68. 输出 formula

必须：

```text
assignment
-> MacroDag
-> Phase2 expandCanonical
-> FormulaDag
-> renderer
```

不要直接从 solver variables拼 LTL string。

---

# 69. Baseline safety

没有 `--macro`：

- 不运行 analyzer；
- 不建 fiber catalog；
- 不改 solver；
- 不改 output；
- 不改 objective。

必须回归测试。

---

# 70. Safe AUTO fallback

原则：

```text
不确定 => original
```

包括：

- unknown raw Alloy；
- unsupported objective；
- concrete internal unary identity；
- exact path length；
- arbitrary closure；
- U。

---

# 71. 不要 catch-all fallback

禁止：

```text
catch(Exception) -> original
```

Capability Unsupported才能 fallback。

进入 Macro solver后的 bug必须暴露。

---

# 72. Macro UNSAT 不是 fallback signal

Supported + 当前 B,b 下 Macro UNSAT：

```text
就是 UNSAT
```

不能再跑 original得到 SAT然后覆盖结果。

binary budget必须在 metadata中明确。

---

# 73. Generic FO fallback 当前不要实现

前期审计说明 generic rank-2/rank-3 type state数过大、压缩价值弱。

Phase 3只保留 specialized profiles。

---

# 74. Macro debug dump

建议 `--macro-debug` 输出：

```text
analysis.json
constraint_states.txt
fiber_catalog.txt
macro_assignment.txt
reconstructed_formula.txt
verification.json
```

内容 deterministic。

---

# 75. 关键 code invariant

A. 所有非-anchor unary syntax只存在于 fiber representative。  
B. Fiber semantic由 SemanticType决定。  
C. Fiber qIn/qOut和 target/source state一致。  
D. 只有 anchors有 shareable identity。  
E. direct edge iff `nonEmpty=false`。  
F. expanded size精确等于 reconstructed FormulaDag size。  
G. decode+expand后 independent verifier接受。

---

# 76. 必须做 size equality test

每个 Macro solution：

```text
modelExpandedSize == expandCanonical(macroDag).size()
```

必须严格相等。

---

# 77. 必须做 edge semantic equality test

对每个 decoded fiber，在小 lassos上比较：

```text
SemanticType evaluator
vs
representativeWord逐 operator evaluator
```

逐 position相等。

---

# 78. 必须做 q-state equality test

每条 edge：

```text
catalog.qIn == state(target)
catalog.qOut == replay(qIn, representative).qOut
```

expanded FormulaDag重新 bottom-up后，anchor q states与 assignment相同。

---

# 79. Protected identity round trip

protected：

```text
search slot
-> MacroDag identity
-> FormulaDag NodeId
```

一一对应。

---

# 80. Existing ATLAS sample smoke tests

Phase 3不跑全 benchmark。

只选少量：

```text
1-3 simple/unconstrained
1 recognized constraint
1 small repair
```

证明真实 parser到 Macro solver闭环。

---

# 81. Tiny differential suite

固定：

```text
AP<=2
B<=5
b<=1或2
trace length<=4
```

自动生成至少约 200 个 deterministic/fixed-seed tasks。

比较：

```text
SAT/UNSAT
minimum size
classification
constraint acceptance
```

---

# 82. Repair differential suite

至少约 50 个 tiny protected-edge tasks。

比较：

```text
(keptEdges max, size min)
```

不是 formula string。

---

# 83. UNSAT tests

必须包含：

- contradictory traces；
- constraint + traces UNSAT；
- B too small；
- b too small；
- protected conflict；
- NoDAGReuse conflict。

不能崩溃或 fallback。

---

# 84. Node-budget boundary

已知 minimum size = s：

```text
B=s-1 -> UNSAT
B=s   -> SAT
B>s   -> optimum仍为 s
```

---

# 85. Binary-budget boundary

至少设计：

```text
needs 1 binary:
b=0 UNSAT
b=1 SAT

needs 2 binary:
b=1 UNSAT
b=2 SAT
```

---

# 86. U fallback

AUTO：

```text
fallbackReason=BINARY_TEMPORAL_UNTIL_REQUIRED
```

FORCE：

```text
Unsupported
```

OFF：

```text
original ATLAS正常支持
```

---

# 87. Unknown Alloy constraint

AUTO fallback，FORCE unsupported。

绝不能误当成 no constraint。

---

# 88. No fallback on internal bug

test-only注入 invalid FiberId / decode mismatch。

AUTO也必须 fail。

---

# 89. Build compatibility

继续保持当前：

```text
Java 8
Java 21
Maven
Kotlin 1.7.0
```

以实际 Phase 2 pom为准。

不升级依赖。

---

# 90. 推荐新增 package

概念职责：

```text
cmu.s3d.ltl.macro
├── compile/
│   ├── MacroTaskAnalysis.kt
│   ├── RecognizedConstraintAnalyzer.kt
│   ├── MacroConstraintPlan.kt
│   ├── ConstraintStateRegistry.kt
│   ├── FiberCatalog.kt
│   └── MacroCompilationContext.kt
├── search/
│   ├── MacroSearchConfig.kt
│   ├── MacroSearchEncoding.kt
│   ├── MacroAlloyModelBuilder.kt
│   ├── MacroObjectiveEncoder.kt
│   └── MacroLearningSolver.kt
├── semantics/
│   ├── LassoPrecomputation.kt
│   ├── SemanticTypeEncoding.kt
│   └── MacroTraceSemanticsEncoder.kt
├── identity/
│   ├── MacroIdentityConstraint.kt
│   ├── NoDagReuseConstraint.kt
│   ├── ChildInequalityConstraint.kt
│   ├── ProtectedEdgeConstraint.kt
│   └── ProtectedReachabilityConstraint.kt
├── decode/
│   ├── MacroAssignmentDecoder.kt
│   └── FinalSolutionVerifier.kt
└── cli/
    └── MacroSolverMode.kt
```

按现有仓库风格调整，不重构已完成 Phase 1/2。

---

# 91. 文档交付

完成后生成：

```text
docs/phase3/
├── IMPLEMENTATION_REPORT.md
├── SUPPORTED_FRAGMENT.md
├── ENCODING.md
└── validation/
    ├── TEST_RESULTS.md
    ├── DIFFERENTIAL_RESULTS.md
    └── SMOKE_RESULTS.md
```

---

# 92. SUPPORTED_FRAGMENT.md

必须明确表：

```text
Feature                              Original   Macro
---------------------------------------------------
U-free trace learning                yes        yes
minimum expanded size                yes        yes
NNF                                  yes        yes
CNF/DNF                              yes        yes
required proposition                 yes        yes
recognized liveness template         yes        yes
NoDAGReuse                           yes        yes
left != right                        yes        yes
recognized repair oldSpec            yes        yes
binary temporal U                    yes        fallback/unsupported
arbitrary raw Alloy                  yes        fallback/unsupported
arbitrary objective                  yes        fallback/unsupported
generic rank-3 FO                    yes        unsupported
```

不要笼统声称“supports ATLAS constraints”。

---

# 93. ENCODING.md

必须写清：

1. K；
2. anchor slots；
3. virtual root；
4. ports；
5. target/fiber；
6. acyclicity；
7. reachability；
8. q-state；
9. expanded size；
10. lasso semantics；
11. trace classification；
12. identity constraints；
13. repair objective；
14. decoder；
15. verifier。

---

# 94. Definition of Done

Phase 3 只有以下全部满足才完成。

## Regression

- Phase 1/2 全测试继续通过；
- Java 8/21通过；
- 原 CLI默认行为不变。

## Analysis

- Supported/Unsupported结构化；
- fail-closed；
- U/unknown raw Alloy正确处理。

## Finite domains

- q registry deterministic；
- fiber catalog deterministic；
- replay正确。

## Structural search

- K正确；
- anchor kind/label；
- ports；
- sharing；
- acyclic；
- reachable；
- B/b bounds；
- expanded size。

## Constraint consistency

- qIn == target q；
- qOut正确；
- root accepting；
- protected identity。

## Semantics

- exact lasso；
- SemanticType encoding；
- positive/negative；
- independent differential通过。

## Objective

- min size；
- repair lexicographic；
- size equality。

## Identity

- child inequality；
- NoDAGReuse；
- protected direct edge；
- reachability；
- oldSpec。

## Decode

- assignment -> MacroDag；
- Phase 2 expansion；
- FormulaDag valid；
- verifier全部通过。

## Solver modes

- OFF；
- AUTO；
- FORCE；
- safe fallback；
- internal bug不 fallback。

## Differential

- tiny reference suite；
- SAT/UNSAT一致；
- objective tuple一致；
- boundary tests通过。

## Scope

- 未做正式性能实验；
- 未声称 U 支持；
- 未实现 generic FO types；
- 未替换 backend。

---

# 95. 完成报告必须回答

1. Phase 2 base commit；
2. Phase 3 final commit；
3. 文件列表；
4. analyzer如何读取 constraints；
5. 实际支持 fragment；
6. state registry；
7. state count样例；
8. FiberCatalog count样例；
9. K与slot encoding；
10. acyclicity；
11. reachability；
12. size公式；
13. lasso semantic encoding；
14. identity encoding；
15. repair objective；
16. decoder；
17. verifier；
18. OFF/AUTO/FORCE；
19. fallback reasons；
20. differential test数量；
21. seeds；
22. Java 8/21；
23. real smoke tests；
24. TODO；
25. 与本指引不同的必要调整。

---

# 96. Phase 3 最容易错的十二点

1. `K=p+3b+2` 是 anchor budget，不是 formula size。
2. VirtualRoot 不计 size。
3. 普通 unary nodes 不应重新成为 search nodes。
4. shared/protected unary nodes必须允许成为 anchor。
5. fiber semantics来自 `SemanticType`。
6. representative syntax只用于 reconstruction/size witness。
7. Fiber必须匹配完整 qIn。
8. empty 与 nonempty identity word不能合并。
9. child equality不能只看 target。
10. NoDAGReuse不能简单统计 incoming ports。
11. AUTO只对 unsupported fallback；bug不能 fallback。
12. bounded-b optimum不能写成 unrestricted optimum。

---

# 97. 给代码大模型的一句话最高层指令

> **在已验收的 Phase 2 分支上，把 MacroDag 从“已求解公式的后处理 representation”升级成真实求解空间：安全识别一组明确支持的 U-free ATLAS constraints/objectives，建立有限 constraint-state 与 FiberCatalog，按 `K=min(B,p+3b+2)` 编码 anchor slots、ports、targets、sharing、q-state consistency、binary/node budgets 和 exact lasso semantics，继续使用原 AlloyMax/OpenWBO backend 求解；将 assignment 解码为 Phase 2 MacroDag，再用现有 canonical expander重建普通 FormulaDag，并由独立 verifier检查 trace、constraint、identity、size 和 repair objective。新增 OFF/AUTO/FORCE 模式，未知 constraints/U 在 AUTO 下安全 fallback，内部 Macro bug不得 fallback。当前阶段只做 correctness、tiny differential tests 和少量 real-input smoke tests，不开展正式性能实验。**

---

# 98. Phase 4 预告：Phase 3 验收后才做

Phase 3 完成后才进入正式实验：

```text
ATLAS baseline reproduction
        |
        v
encoding-size comparison
        |
        v
runtime / solved count
        |
        v
ablation
        |
        v
parameter sensitivity
        |
        v
real benchmark families
        |
        v
synthetic long-unary stress suite
```

Phase 4 才回答：

```text
MacroATLAS 实际减少多少 encoding？
是否提升 constrained LTL learning scalability？
```

Phase 3 只回答：

```text
solver 能否在不损失 correctness / bounded-fragment optimality 的情况下，
直接搜索 MacroDAG？
```
