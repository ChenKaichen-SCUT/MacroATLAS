# MacroATLAS 第一阶段实现报告

本次在本地 ATLAS v1.0.2 上新增 UnaryNormalizer、ConstraintAutomata、FiberTable。
严格遵循上级目录中的 `MacroATLAS_Prototype_Phase1_Implementation_Guide.md`。
模块未接入求解器主路径。

## 1. 基线、范围与源码复用

- 初始 `git status --short` 为空，工作树干净。
- `git rev-parse HEAD`：`f5134d2a3b08e762bf16ebfbd4988a94daa35f88`。
- `git tag --points-at HEAD`：`v1.0.2`。
- 项目实际使用 Kotlin 1.7.0 / Maven，`jvmTarget=1.8`；沿用这些配置。
- `pom.xml`、AlloyMax 1.0.3、原生产代码、原测试和 CLI 均未修改。
- 没有重新 clone 或建立远端 fork：用户提供的本地目录已是指定版本。
- 原项目没有可直接复用的 operator enum。其算子以 task 符号和 Alloy signature
  字符串表示，因此新增小型、有元数区分的 enum，提供 `fromAtlas` 适配。
- 命题复用 `Task.literals: List<String>` 和 `State.values` 中的原始字符串身份，
  不假设存在原项目没有提供的 proposition index，也不做字符串重命名。
- 原 `LTLLearningSolution.Node` 是依赖 Alloy solution 的 DAG 节点描述；
  这三个模块无需另造生产公式 AST。
- 本地论文的 III 节用于核对无限轨迹语义和算子元数，IV/V 节用于核对
  语法约束及 DAG 背景，VI 节用于核对 ATLAS 的 NNF 定义。
  本阶段的 unary 转移表和 fiber 规格来自实现指南。

## 2. 新增文件及职责

以下生产路径均相对于 `src/main/kotlin/cmu/s3d/ltl/macro/`。

| 文件 | 职责 |
| --- | --- |
| `unary/UnaryOperator.kt` | 四种 unary 算子、显式字典序、ATLAS 名称适配 |
| `unary/UnaryWord.kt` | 不可变的外到内 word、prepend、值比较和字典序比较 |
| `unary/TemporalTail.kt` | 五种 canonical tail 及 negation dual |
| `unary/SemanticType.kt` | 不可变 `(xCount, tail, negated)` 值类型 |
| `unary/UnaryNormalizer.kt` | 有限 tail 转移、normalize、prefix、canonicalWord、语义类型比较 |
| `constraint/BinaryOperator.kt` | ATLAS 的 `&, |, ->, U` 及名称适配 |
| `constraint/ConstraintAutomaton.kt` | 通用确定性 bottom-up API 和不可变 state 契约 |
| `constraint/PropositionalAutomaton.kt` | 检查 subtree 不含 `X/F/G/U` |
| `constraint/NnfAutomaton.kt` | 检查 negation 只能直接作用于 atom |
| `constraint/CnfAutomaton.kt` | 指南定义的 propositional CNF |
| `constraint/DnfAutomaton.kt` | 指南定义的 propositional DNF |
| `constraint/RequiredPropositionAutomaton.kt` | 指定原始 proposition 名称是否出现 |
| `constraint/ProductState.kt` | 不可变异构状态 tuple，带所属 product 身份 |
| `constraint/ProductConstraintAutomaton.kt` | 任意数量自动机的惰性乘积、interning、全分量接受 |
| `fiber/FiberKey.kt` | 不可变完整 fiber 身份 |
| `fiber/FiberRepresentative.kt` | 不可变 word witness，长度从 word 派生 |
| `fiber/FiberTable.kt` | 分层 BFS、最短和字典序最小代表、查询、replay |

以下测试路径相对于 `src/test/kotlin/cmu/s3d/ltl/macro/`。

| 文件 | 职责 |
| --- | --- |
| `TestWords.kt` | 独立穷举所有 syntax words 和 shortlex 比较 oracle |
| `UnaryNormalizerTests.kt` | 固定转移、恒等式、87,381 个 word、lasso 真值、不可变性和输入验证 |
| `ConstraintAutomataTests.kt` | 指定示例、全算子覆盖、3,000 个结构随机样本、乘积和状态隔离 |
| `FiberTableTests.kt` | 所有 bound 的完整映射对照、replay、NNF 区分、nonempty、算子子集和边界 |

文档与证据位于 `docs/phase1/`：

| 文件 | 职责 |
| --- | --- |
| `IMPLEMENTATION_REPORT.md` | 本报告、API 用法、复现方式、范围调整和 TODO |
| `validation/baseline-test-summary.txt` | 修改前原 12 个测试的日志摘要 |
| `validation/baseline-cli.csv` | 修改前 README 对应示例的原始 stdout |
| `validation/java8-test-summary.txt` | Java 8 clean verify 的日志摘要 |
| `validation/java21-test-summary.txt` | Java 21 最终 clean verify 的日志摘要 |
| `validation/after-cli.csv` | 修改后相同示例、相同求解器的原始 stdout |
| `validation/TEST_RESULTS.md` | 每项测试的结果、时间及 CLI 对照结果 |

## 3. UnaryWord 与 SemanticType

`[F, X, G]` 始终表示 `F(X(G(hole)))`。`operators[0]` 是最外层，
normalize 和约束 replay 都从尾部向头部执行，即 `G → X → F`。

`SemanticType` 是 Kotlin `data class`：

```kotlin
data class SemanticType(
    val xCount: Int = 0,
    val tail: TemporalTail = TemporalTail.ID,
    val negated: Boolean = false
)
```

含义为 `X^xCount tail !^negated`；tail 为 `ID/F/G/FG/GF`，
例如 `(2, FG, true)` 的 canonical word 是 `[X, X, F, G, !]`。
构造时检查 `xCount >= 0`，prefix X 使用 checked integer addition。

规范化通过一次从内到外的确定性状态扫描实现。没有反复字符串 rewrite。
`UnaryWord` 防御性复制输入集合并使用不可修改的 List；值相等和 hash 一致。
`canonicalWord` 只保持语义，不保证保持语法约束，不能直接取代 fiber witness。

## 4. ConstraintAutomaton API 和自动机

```kotlin
interface ConstraintAutomaton<S : Any> {
    fun literalState(proposition: String): S
    fun unaryState(operator: UnaryOperator, child: S): S
    fun binaryState(operator: BinaryOperator, left: S, right: S): S
    fun isAccepting(state: S): Boolean
}
```

状态要求 immutable，具有稳定的 equality/hash，转移在自己的状态域上确定且完备。
基础自动机均使用 enum state。

| 自动机 | 状态 | 接受条件 |
| --- | --- | --- |
| Propositional | `PROP, NON_PROP` | `PROP` |
| NNF | `ATOM, VALID_NON_ATOM, INVALID` | 前两者 |
| CNF | `ATOM, CLAUSE, CNF, INVALID` | 除 `INVALID` 外 |
| DNF | `ATOM, TERM, DNF, INVALID` | 除 `INVALID` 外 |
| Required proposition | `ABSENT, PRESENT` | `PRESENT` |
| Product | 不可变 component tuple | 所有 component 接受 |

NNF 严格采用 ATLAS 的“negation 只能在 atom 上”定义，因此允许 `->` 和二元 `U`
连接两个合法 child；CNF/DNF 只允许 atom、`!`、`&`、`|`。
`U/Until` 永远不属于 `UnaryOperator`，不能传入 normalizer 或 FiberTable。

Product 接受 `List<ConstraintAutomaton<*>>`，可以组合不同 state 类型；
仅在实际 literal/unary/binary transition 后 intern tuple。`internedStateCount`
可检查惰性行为。空 product 表示恒真约束；也支持嵌套 product。
状态带 owner 身份，拒绝跨 product 误传，异构类型擦除集中在内部一处。
`ConcurrentHashMap` 仅作为私有 interning cache，返回的逻辑状态始终不可变。

## 5. FiberTable BFS、域和 tie-breaking

```kotlin
FiberTable(
    automaton,
    inputStates,
    maxUnaryLength,
    allowedOperators = UnaryOperator.LEXICAL_ORDER
)
```

调用者显式指定需要覆盖的 `inputStates`。基础自动机可传全部 enum values；
product 可传已通过子树转移得到的 reachable states。这避免为通用接口强行加入
“枚举全部 Q”的方法，也不会物化全笛卡尔积。表只对所传入的输入状态域保证完备。

每个 qIn 独立从 `(qIn, IDENTITY, false, qIn)` 开始，向外层 prepend 算子。
key 永远保留四项 `(qIn, semanticType, nonEmpty, qOut)`；不按接受状态剪枝。

每层只扩展前层保留下来的 witness。对于已完成层中的 key，已有 witness 必然更短。
对于当前待完成层中的同一个 key，比较所有等长候选并保留字典序最小 word；
整层比较完毕后才用于下一层扩展。

显式字典序固定为 `! < X < F < G`，word 按外到内比较；最短长度优先。
结果不依赖 HashMap 的迭代顺序或调用者传入的算子顺序。
例如普通 child-first FIFO 可能先遇见 `FX`，但最终代表应为 `XF`。

丢弃同 key 的较差 witness 是安全的：后续相同 prefix 的语义与约束转移完全一致，
同 prefix 也保持长度和字典序的优劣关系。empty/nonempty 分离，保留了非空 identity。

提供 `get(key)`（Kotlin 中缺失为 null）、`keys()`、`size()`、`entries` 和
`replay(qIn, word)`。`replay` 是独立分类工具，允许 word 超出该表的 bound/alphabet/domain；
这种情况下查询结果可能为 null。表和对外集合视图不可修改。

## 6. 使用示例

```kotlin
import cmu.s3d.ltl.macro.constraint.NnfAutomaton
import cmu.s3d.ltl.macro.fiber.FiberTable
import cmu.s3d.ltl.macro.unary.UnaryNormalizer
import cmu.s3d.ltl.macro.unary.UnaryOperator.*
import cmu.s3d.ltl.macro.unary.UnaryWord

val nnf = NnfAutomaton()
val atom = nnf.literalState("x0")
val table = FiberTable(nnf, NnfAutomaton.State.values().toList(), 7)
val a = UnaryWord(NOT, G) // !(G(x0))
val b = UnaryWord(F, NOT) // F(!(x0))

check(UnaryNormalizer.sameSemanticType(a, b))
check(table.replay(atom, a) != table.replay(atom, b))
check(table[table.replay(atom, a)]!!.word == a)
check(table[table.replay(atom, b)]!!.word == b)
```

## 7. 正确性验证范围

- UnaryNormalizer：全部固定等价式、每个 tail/negation 的转移表、canonical type replay；
  对长度 0–8 的全部 **87,381** 个 word 检查 idempotence、canonical 长度不增加、X 数量。
- 独立 lasso oracle：原项目没有 standalone evaluator；新增的 evaluator 仅位于测试内，
  复用原 `LassoTrace/State`。穷举长度 1–4 的 lasso，遍历每个 loop start 和命题取值，
  对长度 0–4 的全部 unary words 比较每个位置的真值；另有 1,000 个固定 seed 样本，
  lasso 长度至 20、word 长度至 64。遍历完整可达循环，不使用有限 horizon 近似。
- ConstraintAutomata：指南全部合法/非法示例，所有算子、INVALID 传播、精确 proposition
  名称、product 惰性/组合/状态归属/immutability；另有 3,000 个固定 seed 公式与独立结构谓词对照。
- FiberTable：对 **每个 B=0…7**，在五个基础自动机全部状态、五自动机乘积的全部可达
  状态、一个允许从拒绝状态恢复的自定义有限自动机，以及空 product 上进行完整映射对比。
  B=7 时每个 qIn 的 brute force 枚举 **21,845** 个 words。
- 每个生成的 fiber 检查 replay、语义类型、nonempty、qOut、长度上界和允许算子。
  独立 brute force 不调用 table 的 BFS 或 replay，字典序比较也使用独立实现。
- 穷举全部 16 种允许算子子集（B=5），验证输入集合顺序和重复元素不影响代表。
- 显式回归：`!G` 与 `F!` 语义相同、NNF state 不同、fiber 和代表不同；
  empty 与 `!!` 保持不同 fiber；较差 first-discovered 代表能被替换。

逐项结果和构建证据见 [validation/TEST_RESULTS.md](validation/TEST_RESULTS.md)。

## 8. 构建和复现

在 `ATLAS` 目录下，用 JDK 8 或以上版本和 Maven 运行：

```bash
mvn -B clean verify
```

仅运行新模块的测试：

```bash
mvn -B -Dtest=UnaryNormalizerTests,ConstraintAutomataTests,FiberTableTests test
```

从源码构建产物运行 README 中的同一个示例（Linux/WSL bash）：

```bash
mvn -B dependency:build-classpath -Dmdep.outputFile=target/runtime-classpath.txt -DincludeScope=runtime
java -Djava.library.path=./lib \
  -cp "target/classes:lib/AlloyMax-1.0.3.jar:$(cat target/runtime-classpath.txt)" \
  cmu.s3d.ltl.app.CLIKt \
  -f src/test/resources/samples2ltl/example0000.trace -s OpenWBOWeighted -T 60
```

原 pom 的普通 JAR 不是包含全部依赖的 release fat JAR；这里使用 classpath 运行同一个
`CLIKt`。`AlloyMax` 是原项目的 system dependency，显式列入 classpath。
原 `lib/open-wbo` 已存在且可执行，无需启动 GUI 或下载其他 solver。
本次仅由 Maven 下载原 pom 所指定的依赖；额外下载并校验 Temurin 8u462 用于兼容性验证，
解压在 `/tmp/macroatlas-jdk8`，未改变系统默认 Java 或仓库依赖版本。

## 9. 与指引的结构调整和剩余 TODO

1. 采用原仓库的 Kotlin 和 Maven 布局，未按示意 Java 文件扩展名实现。
2. 原项目没有 operator enum，新增适配 enum；命题复用原始 String。
3. `get` 的缺失值用 Kotlin nullable 返回代替 Java `Optional`。
4. FiberTable 显式接收 `inputStates`，以适配未提供全状态枚举 API 的通用自动机及惰性 product。
5. Product state 加入 owner 防止异构 state 跨实例误用；对同一实例的 tuple 值相等和 interning 不变。
6. 指南中的普通 BFS 细化为“整层完成等长 tie 后扩展”，保证外层 prepend 时的字典序正确性。
7. 原 README 演示行中的 maxNumOfOP 为 2；仓库实际 TaskParser 对示例 depth=2 计算为 3。
   回归保留仓库实际输出，未为匹配文档演示而修改 baseline。

第一阶段无遗留实现 TODO。后续的 MacroDAG、Anchor extraction、macro edge compiler、
AlloyMax/MaxSAT 集成、公式重建和论文实验，均属于指南明确推迟的后续阶段。
