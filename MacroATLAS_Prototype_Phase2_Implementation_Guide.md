# MacroATLAS Prototype 第二阶段代码实现指引
## 目标：把 Phase 1 接入真实 ATLAS syntax DAG，并实现可验证的 MacroDAG 压缩—重建闭环

> 起点是已经完成并提交的 Phase 1：`UnaryNormalizer + ConstraintAutomata + FiberTable`。  
> 本阶段实现表示层与正确性闭环，不改写 AlloyMax 搜索编码，不开展性能实验。

---

# 0. 结论先行：Phase 2 到底做什么

上一份 Phase 1 指引只在“后续阶段预告”中列出了：

```text
MacroDAG / Anchor extraction
    -> fiber-labelled macro edges
    -> AlloyMax integration
```

它没有规定 Phase 2 的数据结构、算法、边界条件和验收测试，因此不足以直接指导实现。

本阶段应完成下面这条完整但仍与求解器解耦的流水线：

```text
真实 ATLAS LTLLearningSolution
        |
        v
不可变 FormulaDag
        |
        +--> bottom-up constraint-state evaluation
        |
        v
Eligibility + parent/share analysis
        |
        v
Anchor extraction + maximal unary paths
        |
        v
Fiber-labelled MacroDag
        |
        v
每条 macro edge 换成同 fiber 的最短 representative
        |
        v
重建普通 FormulaDag
        |
        v
结构、constraint state、LTL semantics、protected identity 验证
```

本阶段的核心交付不是“更快的 learner”，而是一个可执行的 correctness oracle：

> 给定一个已经存在的 U-free ATLAS formula DAG，证明代码能够安全压缩 unary chains，并重新展开为语义等价、约束状态相同且保留必要 DAG identity 的普通公式。

只有这条闭环通过后，下一阶段才能把 MacroDAG 直接编码进 AlloyMax/MaxSAT 搜索空间。

---

# 1. 本阶段明确不做什么

本轮不要实现：

1. 新的 AlloyMax / MaxSAT 模型；
2. `--macro` CLI 搜索模式；
3. incremental binary budget `b=0,1,...`；
4. arbitrary Alloy constraint parser；
5. 自动识别所有 ATLAS custom constraints；
6. binary temporal `U` 的 macro normalization；
7. specialized lasso encoding；
8. generic rank-2 / rank-3 FO types；
9. benchmark、cactus plot 或 speedup claim；
10. 对原 ATLAS solver 主路径的重构。

特别注意：本阶段是在 **ATLAS 已求得的公式 DAG 上做后处理与验证**。它本身不会让求解更快，也不能作为最终工具性能结果。

---

# 2. 开始编码前必须核对的仓库状态

代码大模型首先应确认：

```bash
git status --short
git log -3 --oneline --decorate
mvn -B clean verify
```

要求：

- Phase 1 已作为正式 commit 存在，而不是 untracked files；
- Linux 可执行位已经修复；
- 原有 12 个测试和 Phase 1 的 28 个新增测试全部通过；
- `src/main/kotlin/cmu/s3d/ltl/macro/` 中已经存在 Phase 1 API；
- 继续保持 Kotlin 1.7.0、JVM target 1.8、Maven 和原依赖版本；
- 不要 reset、覆盖或重新实现已经验收的 Phase 1。

当前已经验收的实际 API 包括：

```kotlin
ConstraintAutomaton<S>
ProductConstraintAutomaton
UnaryNormalizer
UnaryWord
SemanticType
FiberKey<Q>
FiberRepresentative
FiberTable<Q>
```

Phase 2 必须复用这些类型，不能另造第二套 normalizer、fiber key 或 operator enum。

---

# 3. Phase 2 的理论对象

## 3.1 普通 Formula DAG

一个 formula DAG 是有限有根有向无环图。每个节点恰为以下三类之一：

```text
Literal(proposition)             out-degree 0
Unary(operator, child)           out-degree 1
Binary(operator, left, right)    out-degree 2
```

其中：

```text
UnaryOperator = !, X, F, G
BinaryOperator = &, |, ->, U
```

Formula DAG 表示层可以保留 `U`，因为原 ATLAS 支持它；但 MacroATLAS Phase 2 eligibility 必须拒绝任何含 `U` 的 DAG。

节点的 **identity** 与节点的 **label** 必须分开：

- identity 是 Alloy atom 的完整名字，例如 `G$0`；
- label 是其 operator/literal，例如 `G`；
- 两个 label 同为 `G` 的节点仍可能是不同 DAG 节点。

不能从 `getLTL2()` 返回的字符串重建 DAG，因为字符串展开会丢失共享关系。

## 3.2 Constraint state

给定 Phase 1 的 deterministic bottom-up automaton `A`，每个 DAG node 有唯一状态：

```text
state(literal p) = A.literalState(p)
state(op child) = A.unaryState(op, state(child))
state(op l r) = A.binaryState(op, state(l), state(r))
```

必须 memoize：共享子 DAG 只计算一次。

这里不要求根状态是 accepting。Macro canonicalization 必须保持完整 state，而不是只保持 accept/reject bit。

## 3.3 Macro anchor

Phase 2 使用一个虚拟根 `VirtualRoot`，它不属于原公式，也没有 LTL operator。

实际 DAG node 在以下任一情形下成为 anchor：

1. literal node；
2. binary node；
3. 调用者显式标记的 protected node；
4. indegree 大于 1 的 unary node。

第 4 条不可省略。共享 unary node 若被吞进两条不同 macro edges，重建时会被复制，原 DAG identity 和 sharing 就会丢失。

普通 unary root 若既不 protected 又没有多个 parent，不需要成为实际 anchor；它由 `VirtualRoot` 的 root port 开始的 unary word 吸收。

## 3.4 Port

每个 macro edge 从一个确定的 port 出发：

```text
VirtualRoot.ROOT
UnaryAnchor.CHILD
BinaryAnchor.LEFT
BinaryAnchor.RIGHT
```

Literal anchor 没有 port。

## 3.5 Macro edge

从某个 port 的立即 child 开始，沿 unary nodes 向下，直到遇到下一个 anchor。路径上的非-anchor unary labels 按外到内构成 `UnaryWord`。

例如：

```text
And.left -> F0 -> X0 -> G0 -> x0
```

若中间三个 unary nodes 都不是 anchor，则对应 edge 为：

```text
source = And.LEFT
target = x0
word   = [F, X, G]
```

如果 port 直接指向 anchor，则 word 为空。空 word 不能被非空但语义为 identity 的 word 取代；这正是 `FiberKey.nonEmpty` 必须保留的原因。

---

# 4. 建议新增的 package 与职责

最终文件名可按现有项目风格微调，但职责不要混在一个巨型类中。

```text
cmu.s3d.ltl.macro
├── dag/
│   ├── NodeId.kt
│   ├── FormulaNode.kt
│   ├── FormulaDag.kt
│   ├── FormulaDagValidator.kt
│   ├── FormulaDagRenderer.kt
│   └── AlloySolutionDagExtractor.kt
│
├── analysis/
│   ├── DagConstraintEvaluation.kt
│   ├── DagConstraintEvaluator.kt
│   ├── MacroEligibility.kt
│   └── MacroEligibilityAnalyzer.kt
│
└── kernel/
    ├── MacroAnchor.kt
    ├── MacroPort.kt
    ├── RawMacroEdge.kt
    ├── CanonicalMacroEdge.kt
    ├── MacroDag.kt
    ├── AnchorExtractor.kt
    ├── FiberMacroCanonicalizer.kt
    ├── MacroDagExpander.kt
    └── MacroRoundTripVerifier.kt
```

测试建议放在：

```text
src/test/kotlin/cmu/s3d/ltl/macro/dag/
src/test/kotlin/cmu/s3d/ltl/macro/analysis/
src/test/kotlin/cmu/s3d/ltl/macro/kernel/
```

---

# 5. FormulaDag 的严格规格

建议使用 sealed immutable node types，从类型层面保证 arity：

```kotlin
sealed class FormulaNode {
    abstract val id: NodeId
}

data class LiteralNode(
    override val id: NodeId,
    val proposition: String
) : FormulaNode()

data class UnaryNode(
    override val id: NodeId,
    val operator: UnaryOperator,
    val child: NodeId
) : FormulaNode()

data class BinaryNode(
    override val id: NodeId,
    val operator: BinaryOperator,
    val left: NodeId,
    val right: NodeId
) : FormulaNode()
```

`FormulaDag` 至少包含：

```kotlin
root: NodeId
nodes: Map<NodeId, FormulaNode>
```

并提供：

```text
node(id)
children(id)
parents(id)
indegree(id)
reachableNodes()
postOrder()
size()
```

所有外部集合均应为 immutable snapshot。

## 5.1 Validator 必须检查

1. root 存在；
2. 所有 child ID 存在；
3. 图无环；
4. 所有 `nodes` 都从 root 可达；
5. NodeId 唯一；
6. proposition 非空；
7. left 与 right 可以相同——这是合法 DAG sharing，不能错误拒绝；
8. 构造结果不依赖输入 Map 的 iteration order。

对于 cycle、missing child、unreachable node，应返回结构化错误或抛出带明确原因的 `IllegalArgumentException`，不能栈溢出或静默删节点。

---

# 6. 从真实 LTLLearningSolution 提取 DAG

原代码已经公开：

```kotlin
solution.getRoot()
solution.getNodeAndChildren(node)
```

因此优先新增独立 adapter：

```kotlin
class AlloySolutionDagExtractor {
    fun extract(solution: LTLLearningSolution): FormulaDag
}
```

若实际可见性迫使修改 `LTLLearningSolution`，只允许加入一个薄的只读导出方法；不要改变 `getLTL()`、`getLTL2()`、`next()` 或求解逻辑。

提取规则：

1. `getRoot()` 返回的完整 Alloy atom string 作为 root `NodeId`；
2. DFS/BFS 时对每个 atom 最多调用一次并 memoize；
3. `getNodeAndChildren(atom).name` 只用于判定 label；
4. 有两个 child 时必须映射为 `BinaryOperator.fromAtlas(name)`；
5. 有一个 child 时必须映射为 `UnaryOperator.fromAtlas(name)`；
6. 无 child 时作为 literal，proposition 使用原 name；
7. 完整 atom string 必须保留，不能只存去掉 `$0` 后的 name；
8. 不允许通过递归渲染字符串来推断 sharing。

建议实现一个 deterministic `FormulaDagRenderer`，其普通树形展开格式与 `getLTL2()` 一致，用于回归对照；renderer 仅用于显示和测试，不能作为图 identity 的来源。

## 6.1 真实 ATLAS 集成测试

至少选择一个现有、求解很快的 sample：

```text
src/test/resources/samples2ltl/example0000.trace
```

执行原 learner 后：

```text
solution.getLTL2() == FormulaDagRenderer.render(extract(solution))
```

还应验证：

- 提取 DAG 通过 validator；
- root 和全部 child atom identity 保留；
- 重复引用同一 child 时只产生一个 node；
- 原 CLI 输出不变。

如果真实 sample 恰好没有 sharing，sharing 必须另用手工 DAG 测试。

---

# 7. DagConstraintEvaluator

实现：

```kotlin
class DagConstraintEvaluator<Q : Any>(
    private val automaton: ConstraintAutomaton<Q>
) {
    fun evaluate(dag: FormulaDag): DagConstraintEvaluation<Q>
}
```

结果至少包含：

```text
stateByNode: Map<NodeId, Q>
rootState: Q
```

算法必须按 postorder bottom-up，并对 DAG nodes memoize。

测试至少覆盖：

- literal；
- `!p`；
- `G(!p)`；
- `!(Gp)`；
- binary node；
- left/right 指向同一 child；
- 多个 parents 指向同一 unary subtree；
- NNF、CNF、DNF、Propositional、RequiredProp；
- 一个 `ProductConstraintAutomaton`。

对 product automaton，构建 FiberTable 和 evaluator 时必须复用同一个 product instance；不能把属于一个 owner 的 `ProductState` 传给另一个 product instance。

---

# 8. Macro eligibility

本阶段不分析任意 Alloy text。调用者显式提供：

```text
FormulaDag
ConstraintAutomaton<Q>
protectedNodeIds
allowedUnaryOperators
```

`MacroEligibilityAnalyzer` 至少检查：

1. FormulaDag structurally valid；
2. 不含 `BinaryOperator.UNTIL`；
3. 所有 unary operators 都在 allowed set 中；
4. 每个 protected ID 存在于 DAG；
5. protected ID 没有被错误解释成 operator name；
6. constraint automaton 可以对完整 DAG 完成 total evaluation。

返回结构化结果，例如：

```kotlin
sealed class MacroEligibility {
    data class Eligible(...) : MacroEligibility()
    data class Unsupported(val reasons: List<Reason>) : MacroEligibility()
}
```

不要遇到 `U` 后静默忽略该子树，也不要自动 fallback 而不告诉调用者原因。真正的 original-ATLAS fallback 属于后续 CLI 集成阶段。

## 8.1 当前支持的 constraint envelope

本阶段只声称支持：

1. 由传入 `ConstraintAutomaton` 完整观察的 bottom-up syntactic properties；
2. 显式 protected nodes 的 identity 与 label；
3. macro port 与 target anchor 的连接关系；
4. direct edge 与 nonempty unary path 的区别。

本阶段不能声称支持任意 raw Alloy constraint。若 constraint 引用了某个具体内部 unary atom、精确 path length、精确节点数或其他 identity-sensitive object，该 node 必须显式 protected，或者整个 constraint 必须判为 unsupported。

---

# 9. AnchorExtractor 的精确算法

先计算每个实际 node 的 parent set。

实际 anchors：

```text
literal
or binary
or protected
or (unary and indegree > 1)
```

再加入一个不属于 `FormulaDag.nodes` 的 `VirtualRoot`。

## 9.1 需要生成的 ports

```text
VirtualRoot              -> ROOT
protected/shared Unary   -> CHILD
Binary                   -> LEFT, RIGHT
Literal                  -> none
```

若一个 protected node 本身是 binary 或 literal，按其真实 arity生成 ports。

## 9.2 从 port 追踪一条 edge

伪代码：

```text
follow(startNode):
    current = startNode
    word = []
    internalIds = []

    while current is not an anchor:
        assert current is UnaryNode
        word.append(current.operator)       // outer to inner
        internalIds.append(current.id)
        current = current.child

    return RawMacroEdge(
        target = current,
        originalWord = UnaryWord(word),
        originalInternalNodeIds = internalIds
    )
```

调用起点：

```text
VirtualRoot.ROOT -> dag.root
UnaryAnchor.CHILD -> unary.child
Binary.LEFT -> binary.left
Binary.RIGHT -> binary.right
```

如果起点已经是 anchor，生成 empty word edge。

## 9.3 必须检查的 decomposition invariants

1. 每个 port 恰有一条 outgoing macro edge；
2. 每条 edge 的 target 是 actual anchor；
3. 每个非-anchor unary node 恰出现在一条 edge 的 `originalInternalNodeIds` 中；
4. edge 内部 node 顺序与 `UnaryWord` 外到内顺序一致；
5. 任何 indegree > 1 的 unary node 都不出现在 edge 内部；
6. protected node 永不出现在 edge 内部；
7. 允许多个 ports 指向同一个 target anchor；
8. 允许 binary node 的 LEFT/RIGHT 指向同一个 target；
9. 结果 deterministic，不依赖 HashMap iteration order。

## 9.4 为什么需要 VirtualRoot

对：

```text
F(X(G(p)))
```

若没有 protected/shared unary node，理想结果应为：

```text
VirtualRoot.ROOT --[F,X,G]--> p
```

而不是强制把最外层 `F` 留作 anchor。这样才能压缩 root unary chain。

## 9.5 同时记录 port-based kernel 的规模证据

本阶段虽然不建立 Alloy 搜索 slots，但 extractor 应生成 `KernelStatistics`：

```text
b = binary anchor 数
p = 调用者显式 protected node 数
u = unary anchor 数
numberOfAnchors
numberOfPorts
numberOfMacroEdges
maxOriginalUnaryLength
originalNodeCount
canonicalNodeCount
```

按上述 port 定义：

```text
numberOfPorts = 1 + 2b + u
```

其中 `1` 是 virtual-root port。除显式 protected unary nodes 外，额外 unary anchors 只可能来自 indegree 大于 1 的 sharing junction。一个由 `b` 个 binary nodes 产生的 rooted DAG 至多需要 `b+1` 个这样的 terminal/junction contributions，因此采用保守预算：

```text
K = p + 3b + 2
```

代码应把以下不等式作为 assertion/test instrumentation：

```text
numberOfPorts <= K
```

这里 `p` 可以保守地计入所有 protected nodes，即使其中某些本来已因 literal/binary/sharing 成为 anchor。这样只会放宽预算，不会破坏上界。

这一统计用于验证后续 Phase 3 的 `O(b+p)` search-kernel 规模；本阶段不要据此预生成 `K` 个 Alloy atoms，也不要把未使用 slots 混进 MacroDag。

---

# 10. 给 macro edge 标注 FiberKey

先用 `DagConstraintEvaluator` 得到原 DAG 每个 actual anchor 的 state。

对一条：

```text
source.port --word--> target
```

定义：

```text
qIn = stateByNode[target]
key = fiberTable.replay(qIn, originalWord)
```

然后从 `FiberTable` 取得：

```text
representative = fiberTable[key]
```

构建 table 时：

```text
inputStates = 所有 edge target 的 distinct qIn
B = 所有 originalWord.length 的最大值
allowedOperators = eligibility 已确认的 operator set
```

由于每个 original word 长度都不超过 `B`，每个 replay 得到的 key 都必须在 table 中；缺失是实现错误，不能悄悄退回原 word。

每条 canonical edge 至少保存：

```text
source
port
target
originalWord
fiberKey
representativeWord
originalInternalNodeIds
```

并断言：

```text
representative.length <= originalWord.length
normalize(representative) == fiberKey.semanticType
representative.isEmpty == !fiberKey.nonEmpty
replay(fiberKey.qIn, representative).qOut == fiberKey.qOut
```

## 10.1 qOut 的额外交叉检查

不能只相信 `FiberTable.replay`。对原图还应交叉验证：

- `VirtualRoot.ROOT`：edge 的 `qOut` 等于原 DAG `rootState`；
- binary LEFT/RIGHT：edge 的 `qOut` 等于该 port 立即 child subtree 的原 state；
- unary anchor CHILD：edge 的 `qOut` 等于该 unary anchor 立即 child subtree 的原 state。

这一步能发现 word 方向反转、错误 target 或错误 port。

---

# 11. MacroDag 的建议结构

概念上至少包含：

```text
virtualRoot
actualAnchors: Map<NodeId, FormulaNode>
edgesByPort: Map<MacroPort, CanonicalMacroEdge<Q>>
protectedNodeIds
originalNodeCount
constraintRootState
```

`MacroPort` 必须把 source identity 与 port kind 一起纳入 equality/hash。例如两个不同 binary anchors 的 LEFT 不是同一个 port。

实际 anchor node 必须原样保留：

- NodeId；
- literal proposition；
- unary/binary operator label；
- port order。

MacroDag 不应保存对可变 `LTLLearningSolution` 或 `A4Solution` 的引用。

---

# 12. 从 MacroDag 重建普通 FormulaDag

实现两个模式最有利于验证：

```text
expandOriginal(macroDag)
expandCanonical(macroDag)
```

## 12.1 expandOriginal

使用 `originalWord + originalInternalNodeIds`，应精确恢复原 DAG：

```text
same root ID
same node IDs
same labels
same children
```

这是 anchor decomposition 的强回归测试。

## 12.2 expandCanonical

每条 edge 使用 `representativeWord`。

若 representative 为：

```text
[F, X, G]
```

则从 source port 到 target 依次插入：

```text
F-node -> X-node -> G-node -> target
```

新 unary node ID 必须：

- deterministic；
- 全局唯一；
- 不与 actual anchor IDs 冲突；
- 与 `(source, port, position)` 稳定关联；
- 不依赖 Map iteration order。

actual anchors 继续使用原 NodeId。原 edge 内部但未 protected 的 unary IDs 可以消失；这正是 quotient 的效果。

VirtualRoot 本身不进入重建后的 FormulaDag：

- root edge 为 empty 时，重建 root 就是 target；
- root edge 非空时，重建 root 是该 chain 的第一个新 unary node。

## 12.3 重建后的硬性性质

```text
canonicalDag.size <= originalDag.size
```

并且：

- 所有 protected IDs 仍存在；
- 所有 actual anchor IDs 和 labels 不变；
- sharing targets 不被复制；
- macro skeleton 的 source-port/target 关系不变；
- empty/nonempty 性质不变；
- graph 仍 acyclic、reachable、arity-correct。

---

# 13. MacroRoundTripVerifier

不要把验证只散落在 tests 中。建议实现一个生产侧 verifier，返回结构化 violation list，供后续 Phase 3 debug 使用。

至少检查：

1. original expansion 与原 DAG 精确相等；
2. canonical expansion 通过 FormulaDagValidator；
3. anchor/protected identity 和 labels 保留；
4. 每条 representative replay 回同一个 FiberKey；
5. original 和 canonical 的 root constraint state 相等；
6. root accepting status 相等；
7. canonical node count 不增加；
8. 重新 extract canonical DAG 后，macro skeleton 和每条 edge 的 fiber key 不变。

最后一项比较的是 skeleton + fiber，不要求新生成的内部 unary NodeId 与第一次相同。

---

# 14. LTL 语义的独立测试 oracle

constraint state 相同不是 LTL 语义测试的替代品。测试目录中应实现一个独立、仅支持当前 U-free fragment 的 lasso evaluator。

对长度为 `m`、loop start 为 `l` 的 lasso，位置集合为 `0..m-1`，successor 为：

```text
i < m-1  -> i+1
i = m-1  -> l
```

对每个 formula node bottom-up 计算长度 `m` 的 Boolean vector：

- literal：读取 valuation；
- `!`、`&`、`|`、`->`：逐位置计算；
- `X`：读取 successor；
- `F`：当前位置沿 successor 可达的有限位置集合上取 OR；
- `G`：同一可达集合上取 AND。

因为轨迹 ultimately periodic，从任一位置最多走 `m` 步就覆盖所有未来可达位置，不需要有限 horizon 近似。

对 original 与 canonical DAG 比较：

```text
all nodes?      不要求
root at every position? 必须完全相同
```

测试 oracle 不得调用 `UnaryNormalizer` 或 FiberTable 来证明自己，否则会形成循环验证。

---

# 15. 必须实现的测试矩阵

## 15.1 FormulaDag validation

- one literal；
- unary chain；
- binary tree；
- shared child；
- left == right；
- missing child 拒绝；
- cycle 拒绝；
- unreachable node 拒绝；
- 输入 Map 顺序变化不影响 postorder/renderer 结果。

## 15.2 真实 ATLAS adapter

- 至少一个 README/sample solution；
- renderer 与 `getLTL2()` 一致；
- DAG validator 通过；
- 原 CLI regression 不变。

## 15.3 Constraint evaluation

- 五个 Phase 1 基础 automata；
- product automaton；
- shared subtree 只计算一次；
- accepting 与 nonaccepting root 都能完整返回 state。

## 15.4 Anchor extraction

必须单独覆盖：

1. 全 unary 公式：一个 virtual-root edge；
2. binary 两侧各有 unary chain；
3. port 直接指向 anchor，产生 empty word；
4. 两个 ports 共享 literal target；
5. 两个 ports 共享 unary target，该 unary node 自动成为 anchor；
6. chain 中一个 protected unary node，把路径切成两条 edges；
7. root unary node 被 protected：virtual-root edge 为空，该 root 是 anchor；
8. `Binary.LEFT == Binary.RIGHT`；
9. 每个非-anchor unary node恰好覆盖一次；
10. 随机改变 nodes Map 插入顺序，结果不变。

## 15.5 Fiber-labelled edges

- `FFp` 可在允许的 profile 下缩为 `Fp`；
- `GGp` 可缩为 `Gp`；
- `!Gp` 与 `F!p` 语义相同但在 NNF profile 下保持不同 fibers；
- empty 与 `!!` 不合并；
- product profile 的完整 state 被保留；
- 每条 representative 不长于 original；
- 所有 qOut 与原 DAG child/root state 交叉一致。

## 15.6 Expansion and round trip

- `expandOriginal(extract(original)) == original`；
- canonical DAG structurally valid；
- protected IDs/labels 保留；
- shared targets 保留；
- root constraint state 完全相同；
- root accept/reject 相同；
- node count 不增加；
- 至少一个 case 严格减少节点数；
- canonical DAG 再压缩后 skeleton/fibers 稳定。

## 15.7 独立语义验证

至少做两层：

1. exhaustive small cases：小公式、小 lasso、所有 loop starts 和 valuation；
2. fixed-seed randomized：包含 DAG sharing、protected-node subsets、多个 automata/product profiles。

建议随机测试不少于 1,000 个合法 U-free DAG/lasso 组合。失败时必须打印 seed 和最小必要结构，保证可复现。

## 15.8 U 与 unsupported constraints

- 含 `U` 的 FormulaDag 可以表示、渲染和由 adapter 提取；
- MacroEligibility 必须明确返回 unsupported；
- 不允许进入 AnchorExtractor/Fiber canonicalization；
- raw custom Alloy text 未被识别时，不得假装已得到保护。

---

# 16. 一个端到端手工例子

考虑：

```text
And0.left  = F0
F0.child   = F1
F1.child   = x0

And0.right = G0
G0.child   = G1
G1.child   = x1
```

且无 protected unary nodes、无 sharing unary nodes。

anchors：

```text
And0, x0, x1
```

raw edges：

```text
VirtualRoot.ROOT --empty--> And0
And0.LEFT         --[F,F]--> x0
And0.RIGHT        --[G,G]--> x1
```

若 constraint profile 允许：

```text
[F,F] -> [F]
[G,G] -> [G]
```

canonical expansion 为：

```text
And(F(x0), G(x1))
```

需要同时验证：

- 与原公式在所有 lasso positions 上真值相同；
- root constraint state 相同；
- `And0/x0/x1` identity 保留；
- node count 从 7 减至 5；
- virtual-root empty edge 仍为空。

---

# 17. 一个必须拒绝错误压缩的例子

考虑 NNF profile：

```text
word A = [!, G]
word B = [F, !]
```

两者的 LTL semantic type 相同：

```text
!G(phi) == F(!phi)
```

但当 target 是 atom 时：

```text
!(G(p))  -> NNF INVALID
F(!(p))  -> NNF VALID_NON_ATOM
```

因此 Phase 2 的 macro edge canonicalization 必须通过完整 FiberKey 查询，不能直接调用：

```kotlin
UnaryNormalizer.canonicalWord(...)
```

来替换路径。

---

# 18. 对 arbitrary Alloy constraints 的安全规则

ATLAS 的 `.trace` 文件可以嵌入任意 Alloy constraints，例如：

```text
root.l = Neg0
some named node
exact parent/child identity
subDAG relation
oldSpec edge objective
```

Phase 2 不需要解析这些文本，但必须避免错误宣称。

安全规则是：

```text
没有被 recognized profile 编译进 ConstraintAutomaton 的结构条件，
若依赖具体节点 identity，就必须由调用者把相关节点加入 protected set；
否则当前 macro path 只能标记为 unsupported。
```

`nonEmpty` 只保存“direct edge vs 至少一个 unary node”，并不保存精确 unary path 长度或每个内部 node identity。

后续 Phase 3 才实现 recognized ATLAS constraint templates 与 protected-node discovery。

---

# 19. 确定性与兼容性要求

1. 所有 public data objects immutable；
2. NodeId 与 label 分离；
3. 不依赖 HashMap iteration order；
4. port order 固定为 `ROOT, CHILD, LEFT, RIGHT` 或另一显式文档化顺序；
5. traversal 顺序固定；
6. fresh unary IDs deterministic；
7. Java 8 和 Java 21 均能构建；
8. 不升级依赖；
9. 不改变原 CLI 默认行为；
10. 不修改 Phase 1 的数学语义以迁就新代码。

如果发现 Phase 1 API 确实缺少一个通用只读 helper，可以做最小向后兼容扩展，并在报告中列明；不得复制一套新 API。

---

# 20. Definition of Done

只有下面全部满足，Phase 2 才算完成。

## Build and regression

- `mvn -B clean verify` 通过；
- 原 40 项测试继续通过；
- Java 8 与 Java 21 均通过；
- 原 README sample 的 CLI 输出除时间外不变。

## Real DAG integration

- 能从真实 `LTLLearningSolution` 提取 immutable FormulaDag；
- renderer 与原 `getLTL2()` 一致；
- sharing identity 不经字符串展开而保留。

## Constraint bridge

- Phase 1 automata 能 bottom-up 遍历真实/手工 DAG；
- 每个 node state 可查询；
- product-state owner 使用正确。

## Macro kernel

- anchor/port/maximal unary path decomposition 正确；
- 记录 `b,p,u` 与 port count，并验证 `numberOfPorts <= p+3b+2`；
- shared unary 与 protected nodes 不被吞入 edge；
- 每条 edge 有完整 FiberKey 和最短 representative；
- original expansion 精确恢复原 DAG；
- canonical expansion 节点数不增加。

## Correctness verification

- root constraint state 保持；
- accept/reject 保持；
- protected identity/labels 保持；
- skeleton sharing 保持；
- independent lasso oracle 证明 root semantics 保持；
- exhaustive/randomized round-trip tests 通过。

## Scope discipline

- 没有修改 AlloyMax search encoding；
- 没有增加 `--macro` CLI；
- 没有声称支持 U；
- 没有把任意 Alloy constraints 当作已经支持；
- 没有开始性能实验。

---

# 21. 完成后必须生成的报告

请让代码大模型同时提交：

```text
docs/phase2/IMPLEMENTATION_REPORT.md
docs/phase2/validation/TEST_RESULTS.md
```

报告必须包括：

1. 修改/新增文件列表；
2. 当前 commit 与 Phase 1 起始 commit；
3. FormulaDag 数据结构与 validation policy；
4. 真实 LTLLearningSolution adapter 的 identity 映射；
5. constraint evaluator API；
6. eligibility reasons；
7. anchor 判定规则；
8. virtual root 与 port 规则；
9. unary word 的方向约定；
10. fiber table 的 input states、B 和 allowed operators 如何生成；
11. expandOriginal/expandCanonical 的 ID policy；
12. protected/shared node preservation 证据；
13. exhaustive/randomized test 数量、seed 与结果；
14. Java 8/21 build 结果；
15. 原 CLI regression；
16. 与本指引不一致但因源码结构必须调整之处；
17. 所有剩余 TODO。

不得只报告测试总数；需要列出各类性质实际覆盖了什么。

---

# 22. Phase 3 预告，但本轮不要实现

Phase 2 通过后，下一阶段才是：

```text
recognized constraint analyzer
        |
        v
binary-budget / anchor-slot search model
        |
        v
Macro Alloy generator
        |
        v
temporary trace-semantic expansion
        |
        v
AlloyMax / OpenWBO solving
        |
        v
ordinary LTL formula reconstruction
        |
        v
original ATLAS fallback
```

Phase 3 才会回答“MacroATLAS 是否实际减少 encoding 并加速求解”。Phase 2 回答的是更基础的问题：

> Phase 1 的 fiber 理论能否在真实 ATLAS DAG 上形成一个无歧义、可重建、可机械验证的 quotient representation？

---

# 23. 给代码大模型的一句话最高层指令

> **在已验收的 ATLAS Phase 1 分支上，不改变原求解器行为；新增一个 immutable FormulaDag 和真实 LTLLearningSolution adapter，用 Phase 1 ConstraintAutomaton 对 DAG 做 memoized bottom-up evaluation，按 literal/binary/protected/shared-unary anchors 与 virtual-root ports 唯一分解 maximal unary paths，为每条 path 计算完整 FiberKey 并选择最短代表，随后支持 original/canonical 两种重建，并通过结构、constraint state、protected identity、DAG sharing 和独立 lasso semantics 的严格 round-trip 测试。当前阶段不实现 AlloyMax macro encoding、任意 Alloy constraint parsing、U 支持、CLI 或实验。**

---

# 24. 最容易实现错的六点

1. **不能从公式字符串重建 DAG**：那会丢失 sharing。
2. **共享 unary node 必须成为 anchor**：否则重建会复制 identity。
3. **root unary chain 要从 VirtualRoot port 开始压缩**：不要无故保留最外 unary node。
4. **word `[F,X,G]` 是外到内**：bottom-up replay 是 `G -> X -> F`。
5. **替换必须按完整 FiberKey**：不能只按 SemanticType。
6. **raw Alloy constraint 默认不是已支持**：未编译进 automaton 或 protected set 的 identity 条件必须拒绝，而不是猜测。

这六点中任意一点错误，都不足以进入 Phase 3。
