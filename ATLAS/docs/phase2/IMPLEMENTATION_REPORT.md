# MacroATLAS Phase 2 实现报告

已完成真实 ATLAS solution → FormulaDag → constraint evaluation → anchor decomposition →
fiber-labelled MacroDag → original/canonical expansion → round-trip verification 的闭环。
这是既有解的后处理和正确性验证，没有改变 AlloyMax 搜索编码、CLI 默认行为或依赖版本。

## 1. 版本与验收状态

- Phase 1 起始提交：`920836e2b2b4d61820be6d39da5b731c757e3b23`。
- 当前已验证的 Phase 2 **代码提交**：`0a654f36f49a5ccf89a7bf099f8e8e486265ed52`。
  本报告、验证记录及 README 更新在随后的文档提交中；该提交不改动已验证代码。
- 开始时仅有用户新增的 Phase 2 指南未跟踪；Phase 1 已正式提交。
- 修改前 `mvn -B clean verify`：原 40 项全部通过。
- 修改后 Java 8 / Java 21 `clean verify`：均为 **72 项通过，0 失败、0 错误、0 跳过**。
- README 对应 CLI sample 修改前后都得到 `!(F(x0))`；表头及全部非时间字段完全相同。
- 25 个原 solver/parser/Phase 1/依赖配置文件逐字节保持不变。
- OpenWBO 内容未改；Git 文件模式由 `100644` 修正为 `100755`，保证 Linux clone 后可执行。
  原工作区文件本身此前已有执行权限，但提交中的执行位缺失。

完整日志摘要与逐项结果见 [validation/TEST_RESULTS.md](validation/TEST_RESULTS.md)。

## 2. 新增和修改文件

生产文件相对 `src/main/kotlin/cmu/s3d/ltl/macro/`，共 21 个：

| 文件 | 职责 |
| --- | --- |
| `dag/NodeId.kt` | 完整节点 identity 和固定排序，独立于 operator/literal label |
| `dag/FormulaNode.kt` | Literal/Unary/Binary 三种不可变节点及有序 child references |
| `dag/FormulaDag.kt` | 严格验证的不可变 rooted DAG，parents/indegree/postorder 等只读查询 |
| `dag/FormulaDagValidator.kt` | root、引用、标签、重复身份、cycle、reachability 检查 |
| `dag/FormulaDagRenderer.kt` | 与 getLTL2 一致的显示用展开，不用于恢复图结构 |
| `dag/AlloySolutionDagExtractor.kt` | 只读调用真实 LTLLearningSolution 的 atom/root 导出 API |
| `dag/Snapshots.kt` | 包内使用的防御性不可变集合快照 helper |
| `analysis/DagConstraintEvaluation.kt` | 所有节点的完整 constraint state 与 root state 快照 |
| `analysis/DagConstraintEvaluator.kt` | memoized bottom-up 求值，每个 actual node 只转移一次 |
| `analysis/MacroEligibility.kt` | Eligible/Unsupported、原因枚举及显式拒绝异常 |
| `analysis/MacroEligibilityAnalyzer.kt` | 检查片段、allowed alphabet、protected identity 和约束覆盖边界 |
| `kernel/MacroPort.kt` | VirtualRoot、端口种类、source+kind 身份和确定性排序 |
| `kernel/RawMacroEdge.kt` | 原始 unary word 与对应的内部节点身份 |
| `kernel/CanonicalMacroEdge.kt` | 原始 edge、完整 FiberKey、最短 representative |
| `kernel/KernelStatistics.kt` | b/p/u、节点/端口/edge 数量及 port budget 检查 |
| `kernel/RawMacroDag.kt` | 尚未挑选代表的不可变 anchor decomposition |
| `kernel/MacroDag.kt` | fiber-labelled 宏图快照与统计 |
| `kernel/AnchorExtractor.kt` | anchor 提取、maximal unary paths、覆盖与重建 invariant |
| `kernel/FiberMacroCanonicalizer.kt` | 复用 Phase 1 FiberTable 选择最短代表并核对原图 port state |
| `kernel/MacroDagExpander.kt` | 保留原 ID 的原始重建、分配新内部 ID 的 canonical 重建 |
| `kernel/MacroRoundTripVerifier.kt` | 生产侧结构化 violation 收集及二次压缩稳定性检查 |

测试文件相对 `src/test/kotlin/cmu/s3d/ltl/macro/`，共 7 个：

| 文件 | 职责 |
| --- | --- |
| `dag/TestDags.kt` | 手工 identity graph fixture，测试中不解析公式字符串 |
| `dag/FormulaDagTests.kt` | 结构、无环、deep graph、共享、顺序无关性和不可变性 |
| `dag/AlloySolutionDagExtractorTests.kt` | 真实 solution/真实 sharing/U 提取、memoization 和错误 arity |
| `analysis/DagAnalysisTests.kt` | 全部 Phase 1 profiles、完整状态、单次求值及 eligibility 拒绝路径 |
| `kernel/MacroKernelTests.kt` | anchor/port/fiber/身份/重建/碰撞/确定性和 verifier 的错误诊断 |
| `kernel/UFreeLassoOracle.kt` | 测试专用独立无限 lasso 求值器 |
| `kernel/MacroSemanticsTests.kt` | 穷举、随机、oracle 固定真值和真实 sample 分类回归 |

其他文件：

| 文件 | 改动 |
| --- | --- |
| 根目录 `MacroATLAS_Prototype_Phase2_Implementation_Guide.md` | 收录用户提供的原始第二阶段规格 |
| `lib/open-wbo` | 仅修正 Git executable bit；二进制内容不变 |
| 根目录 `README.md` | 描述两个阶段、链接 Phase 2 规格和报告 |
| `UPSTREAM.md` | 补充 Phase 2 目录及 OpenWBO 模式修正说明 |
| `docs/phase2/IMPLEMENTATION_REPORT.md` | 本实现报告和 API 用法 |
| `docs/phase2/validation/TEST_RESULTS.md` | 全部测试及完成标准的逐项证据 |
| `docs/phase2/validation/baseline-test-summary.txt` | 改动前 40 项测试摘要 |
| `docs/phase2/validation/java8-test-summary.txt` | Java 8 最终 72 项测试摘要 |
| `docs/phase2/validation/java21-test-summary.txt` | Java 21 最终 72 项测试摘要 |
| `docs/phase2/validation/baseline-cli.csv` | 修改前 CLI stdout |
| `docs/phase2/validation/after-cli.csv` | 修改后相同命令的 CLI stdout |

## 3. FormulaDag 数据结构与 validation policy

`NodeId(value: String)` 保留完整身份；节点是 sealed `FormulaNode` 的三个 immutable data class：

```text
LiteralNode(id, proposition)
UnaryNode(id, UnaryOperator, child)
BinaryNode(id, BinaryOperator, left, right)
```

算子和 proposition 使用 Phase 1 的现有类型与 ATLAS 的原始 String，不另建 enum 或 formula parser。
`FormulaDag(root, nodes)` 对 Map 做防御性复制并按 NodeId 排序，构造时完成全部 validation：

- root 和所有 children 存在；Map key 必须等于 node.id；proposition 非空白。
- collection 构造器在转成 Map 前检查重复 NodeId，避免被 associate 静默覆盖。
- iterative DFS 检查 cycle 并生成 children-before-parent postorder。
- 所有节点必须从 root 可达；不会静默丢弃 unreachable nodes。
- binary LEFT 和 RIGHT 可以指向同一个 NodeId。
- children 固定 LEFT→RIGHT；postorder 与输入 Map 的插入顺序无关。
- 对外的 map、list、set 都是不可修改的独立快照。

构造失败抛出带明确原因的 `IllegalArgumentException`。
可用查询为 `node`、`children`、`parents`、`indegree`、`reachableNodes`、`postOrder`、`size`。
graph equality 比较 root、全部 ID、label 及 children，完全保留 sharing。
12,001 节点深链和同深度 cycle 已测试，无递归栈溢出。

**共享计数的必要澄清：** `parents(id)` 返回不同父节点的集合；`indegree(id)` 计算入边端口数。
例如 `b.left = b.right = u` 时，parents 只有 `{b}`，但 indegree 是 2。
如果以 distinct parents 数量代替 indegree，u 会被错误吞入两条 edges，破坏唯一覆盖和 sharing。
因此本实现按 port 数识别共享 unary，并有专门回归和真实 Alloy sharing 测试。

## 4. 真实 LTLLearningSolution adapter

`AlloySolutionDagExtractor.extract(solution)` 只调用现有公开方法：

```text
getRoot()
getNodeAndChildren(fullAtomString)
```

从 root 迭代遍历，每个完整 atom 最多读取一次。`G$0` 等完整字符串作为 NodeId；
`Node.name` 仅决定 label。literal 不去掉 proposition 名称中的数字；operator signature 的
末尾数字按原 `getLTL2()` 的规则去掉，例如 `G12` 适配为 unary G。
两个 child 映射到 Phase 1 BinaryOperator，一个左 child 映射到 UnaryOperator，
无 child 映射到 Literal。仅有 right child 的异常节点被拒绝。

没有调用 `getLTL2()` 来推断结构，也没有修改 `LTLLearningSolution`。
真实测试包括：

1. `example0000.trace`：renderer 与 getLTL2 相同，root/child atom IDs 逐项对应，并完成 macro round trip。
2. 一个受约束的真实 Alloy solution 强制 AND 的两端共享同一 NEG unary node：提取仅 4 个 nodes，保留同一 child ID。
3. `example0007.trace`：含 U 的解可以提取、渲染；macro eligibility 明确拒绝。

第二项的 raw custom constraints 也被单独传给 eligibility，验证其被拒绝，未宣称已自动识别该 Alloy text。

## 5. Constraint evaluation 与 eligibility

```kotlin
DagConstraintEvaluator(automaton).evaluate(dag)
// 返回 DagConstraintEvaluation(stateByNode, rootState)

MacroEligibilityAnalyzer(automaton).analyze(
    dag,
    protectedNodeIds = emptySet(),
    allowedUnaryOperators = UnaryOperator.LEXICAL_ORDER,
    unhandledAlloyConstraints = null
)
```

求值按 DAG postorder 对每个节点只执行一次转移。保留完整 state，不按 root accepting bit 过滤。
一个 NNF-invalid 根也可以被分析和压缩，只要压缩后仍保持同一个 INVALID 状态。

Eligibility 的结构化拒绝原因：

| Code | 含义 |
| --- | --- |
| `INVALID_STRUCTURE` | 结构校验失败；通常已被严格 FormulaDag 构造器提前拒绝 |
| `UNTIL` | 存在二元 temporal U |
| `DISALLOWED_UNARY` | 原图 unary 算子不在所传 alphabet 中 |
| `UNKNOWN_PROTECTED_NODE` | protected ID 不存在；不会把 `G` 当作 `G$0` |
| `UNHANDLED_ALLOY_CONSTRAINTS` | 存在尚未编译进受支持 profile 的 raw Alloy text |
| `AUTOMATON_EVALUATION_FAILED` | automaton 转移或根 acceptance 查询失败 |

只有 Eligible 能进入 AnchorExtractor；Unsupported 会抛出携带同一原因列表的
`MacroIneligibleException`，不会悄悄 fallback。

**约束覆盖边界：** 这里只保证 supplied automaton 完整观察的 bottom-up property、显式 protected
ID/label、macro port→target anchor 关系，以及 direct edge/nonempty path 区别。
非空 raw Alloy text 无条件拒绝，即使所有节点都 protected，也不推断精确长度、节点数或任意 relational objective。
处理现有 Task 时，在尚无 recognized-profile compiler 的情况下，应传入
`unhandledAlloyConstraints = task.customConstraints`。solution adapter 自身不知道 Task 的文本。
省略该参数表示调用者声明所提供 automaton/protected set 已是此次后处理的完整约束范围。

同一个 automaton instance 从 Eligible 携带到 raw graph、FiberTable、MacroDag 和 verifier。
因此 product state 始终留在同一个 owner 域内，未重新构造一个同配置的 product 来误用状态。

## 6. Anchors、VirtualRoot、ports 和 unary 方向

actual anchor 的判定：literal、binary、显式 protected，或 indegree >1 的 unary。
`VirtualRoot` 是独立对象，没有 NodeId、LTL operator，也不属于 FormulaDag.nodes。
MacroPort 身份是 `(source NodeId?, kind)`；null 只用于 VirtualRoot 的 ROOT。

端口顺序明确为 ROOT、CHILD、LEFT、RIGHT；实际遍历时 VirtualRoot 排第一，
再按 source NodeId、同 source 的 port kind 排序。

- VirtualRoot 有 ROOT，起点为原 dag.root。
- unary anchor 有 CHILD；binary anchor 有 LEFT/RIGHT；literal 没有 port。
- 沿实际 child reference 追踪到下一个 anchor。非-anchor unary labels 形成外到内的 word。
- `[F,X,G]` 表示 `F(X(G(hole)))`；bottom-up replay 执行 G→X→F。
- 直接到达 anchor 的 edge 保持 empty word。

Extractor 检查每个非-anchor unary 恰被覆盖一次、protected/shared unary 不在 edge 内部、
每个 port 恰有一条 edge，并通过 original expansion 核对整个原图精确恢复。
不强制保留普通 unary root；它可以完整进入 VirtualRoot.ROOT 的 word。

`KernelStatistics` 保存 b/p/u、actual anchor 数、port/edge 数、最长原 unary word、
original/canonical node count；anchor count 不含 VirtualRoot，p 是去重后的全部显式 protected IDs。
生产侧使用 `check`（不依赖 JVM `-ea`）验证：

```text
numberOfPorts = 1 + 2*b + u
numberOfPorts = numberOfMacroEdges
numberOfPorts <= p + 3*b + 2
```

不分配预留 Alloy slots，也不把这个计数当作速度提升结果。

## 7. FiberTable 桥接

只复用 Phase 1 的 FiberTable、FiberKey、UnaryWord 和 normalizer：

```text
inputStates = 每条 edge target 的原 constraint state，去重
B           = 所有原 edge word 的最大长度
allowed     = eligibility 已验证的 unary alphabet
key         = table.replay(targetState, originalWord)
rep         = table[key].word
```

任何缺失 fiber 是实现错误，直接失败；没有退回原 word。
每条 rep 都验证完整 replay key、长度不增加、semantic type 和 nonEmpty。
额外交叉核对 qOut：它必须等于原图中该 port 立即 child 的状态；VirtualRoot 的 qOut 则必须等于原 rootState。
因此状态核对不只在 FiberTable 自己内部循环完成。

`!G` 和 `F!` 在 NNF atom target 上仍是不同 fibers；empty 与非空 semantic identity 也不合并。
代表的 tie-breaking 完全沿用 Phase 1 的最短长度优先及 `! < X < F < G`。

## 8. 重建 ID policy 与 verifier

`expandOriginal(raw)` 和 `expandOriginal(macro)` 使用原 word 和原 internal IDs，
精确恢复 root、全部节点身份、label、children 和共享。

`expandCanonical(macro)`：

- actual anchors 继续使用原 ID 和 label，按 port 重接 child。
- unary representative 用外到内的位置分配新 ID，再从内到外连到同一 target anchor。
- 新 ID 形式是 `__macro__/<source-token>/<port-kind>/<position>`；source-token 对实际 NodeId
  加长度前缀，与 virtual source 区分。候选与任一原节点 ID 碰撞时，确定性增加 `~1`、`~2` 等 suffix。
- 所有 ports 按固定顺序处理，不依赖 HashMap 顺序；不复制共享 target。
- 原未 protected 的内部 ID 可以消失；VirtualRoot 不会变成普通公式节点。
- root edge 为空则 target 是新 root，否则该 edge 的第一个新 unary node 是新 root。

新图通过 FormulaDag 的同一严格 validation。每条 edge 的代表不增长，且其内部原 IDs 互不重叠，
因此 `canonicalDag.size <= originalDag.size`。手工 AND(FF(x0),GG(x1)) 从 7 节点变为 5 节点。

生产 `MacroRoundTripVerifier.verify(original, macro)` 返回 immutable violation list 和 canonicalDag。
它检查原图精确重建、canonical 结构、anchor/protected ID 与 label、完整 fiber replay、
原/新 port state、root state 与 acceptance、节点数和 port budget，以及重新提取后的 skeleton/fiber 稳定。
还核对二次 canonicalization 给出的 representative，发现非最短或错误 tie-break 的 witness。

verifier 成功表示转换保持这些性质，**不等于**根约束被接受；非接受状态同样必须保留。
独立 LTL 真值 oracle 仅存在于测试包，没有成为生产代码依赖。

## 9. 端到端 API 用法

```kotlin
import cmu.s3d.ltl.macro.analysis.MacroEligibilityAnalyzer
import cmu.s3d.ltl.macro.constraint.NnfAutomaton
import cmu.s3d.ltl.macro.dag.AlloySolutionDagExtractor
import cmu.s3d.ltl.macro.kernel.*

val solution = requireNotNull(task.buildLearner().learn())
val dag = AlloySolutionDagExtractor().extract(solution)
val profile = NnfAutomaton()
val eligibility = MacroEligibilityAnalyzer(profile).analyze(
    dag,
    protectedNodeIds = emptySet(),
    unhandledAlloyConstraints = task.customConstraints
)
val raw = AnchorExtractor.extract(eligibility) // Unsupported 时明确抛出结构化异常
val macro = FiberMacroCanonicalizer.canonicalize(raw)
check(MacroDagExpander.expandOriginal(macro) == dag)
val result = MacroRoundTripVerifier.verify(dag, macro)
check(result.isValid) { result.violations.toString() }
val canonical = requireNotNull(result.canonicalDag)
```

## 10. 测试覆盖与结果

新增 32 项测试，原 40 项继续通过；Java 8 和 Java 21 均完整运行全部 72 项。
各类性质详见 [测试报告](validation/TEST_RESULTS.md)，主要数量如下：

- 60 个小 DAG：两命题上所有语法 size≤3 的 U-free 树公式，另加 6 个共享 unary 的 DAG。
- 穷举其每个 protected subset 和 6 种 base/product profiles，共 **2,616 次 round trip**。
- lasso 长度 1–2，所有 loop starts、p/q 的所有 valuation，共 36 个 lassos；比较 root 的每个位置，
  合计 **94,176 次 Boolean vector 对照**。
- 独立 oracle 按节点 bottom-up 求值，F/G 遍历完整可达循环，不使用有限 horizon 近似；
  不调用 UnaryNormalizer、FiberTable 或 macro 实现来建立真值。
- 随机 seed=`20260921`，**1,200** 个合法 U-free DAG/lasso/profile/protected-set 组合，
  生成池最多 26 个节点、lasso 长度至 12；每例另外反转 Map 插入顺序检查同一 canonical DAG。
- 随机案例中 sharing=643、非空 protected set=817、严格减少节点=76。
  失败信息带 seed、iteration、DAG、protected IDs 和 lasso；这些数字为正确性覆盖，不是 benchmark。
- 手工 `!G/F!`、empty/`!!`、binary LEFT==RIGHT、protected root/interior、fresh ID 碰撞都单独覆盖。
- verifier 的错误路径通过损坏 word、缺少 port、改变 anchor label、缺失 protected identity、
  假节点数、错 root state 和非最短 representative 单独验证。
- 原 CLI 相同 sample、同一个 OpenWBOWeighted、相同 classpath/参数前后对照通过。

## 11. 构建与 CLI 复现

在 `ATLAS/` 目录，用 Java 8 或以上及 Maven 运行：

```bash
mvn -B clean verify
```

只运行新增的 Phase 2 tests：

```bash
mvn -B -Dtest=FormulaDagTests,AlloySolutionDagExtractorTests,DagAnalysisTests,MacroKernelTests,MacroSemanticsTests test
```

运行原 README sample（Linux/WSL）：

```bash
mvn -B dependency:build-classpath -Dmdep.outputFile=target/runtime-classpath.txt -DincludeScope=runtime
java -Djava.library.path=./lib \
  -cp "target/classes:lib/AlloyMax-1.0.3.jar:$(cat target/runtime-classpath.txt)" \
  cmu.s3d.ltl.app.CLIKt \
  -f src/test/resources/samples2ltl/example0000.trace -s OpenWBOWeighted -T 60
```

环境为 Maven 3.6.3、Kotlin 1.7.0，JVM target 1.8、AlloyMax 1.0.3；依赖没有升级。
Java 8 使用 `/tmp/macroatlas-jdk8/jdk8u462-b08`，仅为验证进程设置 JAVA_HOME/PATH；
默认系统 Java 21.0.12 保持不变。最终全部 49 个 Phase 2 class 文件均检查为 major version 52。

## 12. 与指南的调整及剩余 TODO

1. **indegree 按入边端口计数**，parents 仍是 distinct parent set。该澄清解决同一父节点 LEFT==RIGHT
   指向 unary 时的共享丢失，与指南的唯一分解和 identity preservation 要求一致。
2. 没有额外 MacroAnchor wrapper：actualAnchors 直接保留原 FormulaNode；VirtualRoot 与 MacroPort
   定义在同一文件。这样避免重复存储 anchor label/identity。
3. 增加 `RawMacroDag`、`KernelStatistics` 和包内 immutable snapshot helpers，分离阶段和职责。
4. 原 `LTLLearningSolution` API 已足够，无需增加导出方法或修改其源码。
5. eligibility 显式接收 `unhandledAlloyConstraints`，对非空文本采取保守拒绝；不自行识别 raw Alloy。
6. fresh IDs 额外避开全部原 internal IDs，强于只避开 actual anchors；重压缩不要求新内部 IDs 相同。
7. 补齐前一提交漏记的 OpenWBO 执行位，文件内容保持不变。

Phase 2 没有剩余实现 TODO。任意 Alloy constraint 解析、recognized-profile 编译和 protected discovery、
Macro Alloy/MaxSAT 搜索模型、binary-budget search、CLI macro 模式及性能实验均留待 Phase 3。
