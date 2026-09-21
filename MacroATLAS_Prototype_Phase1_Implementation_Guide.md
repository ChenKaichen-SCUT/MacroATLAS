# MacroATLAS Prototype 第一阶段代码实现指引
## 目标：在 ATLAS ICSE 2025 官方代码基础上实现 UnaryNormalizer + ConstraintAutomata + FiberTable
> 当前阶段只实现并测试三个基础模块，不实现实验、不重写 ATLAS 主求解器、不实现完整 MacroDAG/MaxSAT 编译。  
> 后续阶段将在这三个模块通过严格单元测试后再继续。

# 项目背景

ATLAS 搜索满足：

1. positive / negative lasso traces；
2. 用户给定的 syntactic / relational Alloy constraints；
3. 用户给定 optimization objectives；

的 LTL formula。

一个核心问题是：

> ATLAS 在 syntax DAG 空间中搜索，大量不同 syntax 可以表示同一个 LTL 语义。

例如：

\[
FF\varphi \equiv F\varphi,
\qquad
GG\varphi \equiv G\varphi.
\]

但是不能简单地“每个 semantic equivalence class 只留下一个公式”，因为 ATLAS constraint 可能区分两个语义等价但语法不同的公式。

例如：

\[
\neg Gp \equiv F\neg p,
\]

但如果 constraint 要求 NNF，则后者合法，前者不合法。

因此我们研究的不是普通：

```text
semantic quotient
```

而是：

```text
constraint-preserving semantic quotient
```

第一阶段需要实现的三个组件正是后续 quotient compiler 的基础：

```text
UnaryNormalizer
        +
ConstraintAutomata
        +
FiberTable
```

---

# 3. 当前已经证明并冻结的理论范围

当前 prototype 第一版只针对：

\[
\boxed{\text{U-free LTL}}
\]

也就是 temporal unary operators：

```text
!, X, F, G
```

以及以后由 macro skeleton 处理的 Boolean binary operators，例如：

```text
&, |, ->
```

当前阶段：

```text
U
```

不参与 UnaryNormalizer / FiberTable。

如果 ATLAS 原有 operator 类型中存在 `U`，必须保留原项目支持，但 MacroATLAS 第一阶段的 unary quotient 模块不得把 `U` 当作 unary operator，也不得声称支持 `U` 的 normalization。

---

# 4. UnaryNormalizer 的数学规格

## 4.1 Unary word

把一个 unary context 写成：

\[
w=o_1o_2\cdots o_m,
\qquad
o_i\in\{\neg,X,F,G\}.
\]

这里的顺序约定是：

```text
[o1, o2, ..., om]
```

表示：

\[
o_1(o_2(\cdots o_m(\Box)\cdots)).
\]

即 list 的第一个 operator 是最外层。

例如：

```text
[F, X, G]
```

表示：

\[
F(X(G(\Box))).
\]

代码中必须把这个方向写进注释，并始终统一。

---

## 4.2 Canonical semantic type

每个 unary word 都归约为一个 semantic type：

\[
\boxed{
X^k \tau \neg^\epsilon
}
\]

其中：

\[
k\ge 0,
\]

\[
\tau\in\{I,F,G,FG,GF\},
\]

\[
\epsilon\in\{0,1\}.
\]

建议代码结构：

```text
SemanticType
    int xCount
    TemporalTail tail   // ID, F, G, FG, GF
    boolean negated
```

其中 `tail` 的字符串顺序依然是外到内：

```text
FG = F(G(hole))
GF = G(F(hole))
```

---

## 4.3 使用的 LTL 等价式

实现依据：

\[
\neg\neg\varphi\equiv\varphi,
\]

\[
\neg X\varphi\equiv X\neg\varphi,
\]

\[
\neg F\varphi\equiv G\neg\varphi,
\]

\[
\neg G\varphi\equiv F\neg\varphi,
\]

\[
FX^k\varphi\equiv X^kF\varphi,
\]

\[
GX^k\varphi\equiv X^kG\varphi,
\]

\[
FF\varphi\equiv F\varphi,
\]

\[
GG\varphi\equiv G\varphi,
\]

\[
FGF\varphi\equiv GF\varphi,
\]

\[
GFG\varphi\equiv FG\varphi.
\]

因此 F/G-only 部分最终只可能是：

```text
ID
F
G
FG
GF
```

---

# 5. UnaryNormalizer 不要用反复字符串 rewrite 实现

生产实现应使用一个小的确定性状态转换。

从 identity type：

```text
(k=0, tail=ID, neg=false)
```

开始。

为了构造一个外到内 unary word：

```text
[o1, o2, ..., om]
```

建议从 **最内层向最外层** 扫描：

```text
om, ..., o2, o1
```

每一步执行：

```text
prefix(operator, currentSemanticType)
```

---

## 5.1 Prefix X

若：

\[
C=X^k\tau\neg^\epsilon,
\]

则：

\[
XC=X^{k+1}\tau\neg^\epsilon.
\]

即：

```text
xCount += 1
tail unchanged
negated unchanged
```

---

## 5.2 Prefix F

因为：

\[
FX^kC\equiv X^kFC,
\]

只需更新 `tail`：

| old tail | prefix F 后 |
|---|---|
| ID | F |
| F | F |
| G | FG |
| FG | FG |
| GF | GF |

`xCount` 和 `negated` 不变。

---

## 5.3 Prefix G

| old tail | prefix G 后 |
|---|---|
| ID | G |
| F | GF |
| G | G |
| FG | FG |
| GF | GF |

`xCount` 和 `negated` 不变。

---

## 5.4 Prefix NOT

把 negation 向内推。

tail dual：

| old tail | dual |
|---|---|
| ID | ID |
| F | G |
| G | F |
| FG | GF |
| GF | FG |

然后：

```text
negated = !negated
```

`xCount` 不变。

---

# 6. UnaryNormalizer API 建议

首先检查 ATLAS 原源码中已有的数据类型。

若可复用，则适配原类型。不要无意义复制。

逻辑 API 至少需要：

```text
SemanticType normalize(UnaryWord word)

SemanticType prefix(UnaryOperator op, SemanticType state)

UnaryWord canonicalWord(SemanticType state)

boolean sameSemanticType(UnaryWord a, UnaryWord b)
```

其中：

```text
canonicalWord(X^k tau !^epsilon)
```

返回：

```text
X ... X + tail + optional !
```

例如：

```text
(k=2, tail=FG, neg=true)
```

返回：

```text
[X, X, F, G, !]
```

并满足：

```text
normalize(canonicalWord(t)) == t
```

---

# 7. UnaryNormalizer 必须满足的性质

对每个 word `w`：

### P1. Idempotence

```text
normalize(canonicalWord(normalize(w))) == normalize(w)
```

### P2. Canonical length 不增加

```text
canonicalWord(normalize(w)).length <= w.length
```

### P3. Known identities

必须测试：

```text
FF == F
GG == G
FGF == GF
GFG == FG
FX == XF
GX == XG
!X == X!
!F == G!
!G == F!
```

这里 `==` 指 `normalize` 后的 SemanticType 相同，不是 Java object identity。

### P4. Exhaustive small-word test

对：

```text
length <= 8
```

的全部：

\[
1+4+\cdots+4^8=87381
\]

个 unary words：

1. `normalize` 不抛异常；
2. canonical type idempotent；
3. canonical length 不增加；
4. `canonicalWord` replay 回同一 state。

如果 ATLAS 源码已经有 LTL evaluator，则额外随机生成 lassos，比较：

```text
w(phi)
canonical(w)(phi)
```

的 truth value。

这属于测试增强，不应成为生产代码依赖。

---

# 8. ConstraintAutomata 的目的

Semantic type 相同并不意味着在 syntactic constraint 下可互换。

因此每个 subtree 除 semantic information 外，还需要一个有限 constraint state：

\[
q\in Q.
\]

本阶段定义一个通用 deterministic bottom-up automaton abstraction。

建议概念接口：

```text
interface ConstraintAutomaton<S> {
    S literalState(...);
    S unaryState(UnaryOperator op, S child);
    S binaryState(BinaryOperator op, S left, S right);
    boolean isAccepting(S state);
}
```

实际签名应适配 ATLAS 现有 operator / proposition 类型。

如果某个 automaton 不关心 proposition 的名字，可以忽略 literal 参数。

要求 state：

- immutable；
- 正确实现 equality/hash；
- 可安全用作 HashMap key。

---

# 9. 第一阶段至少实现的 automata

## 9.1 Propositional-only automaton

目标：

```text
当前 subtree 是否完全不包含 temporal operator X/F/G/U
```

可用：

```text
PROP
NON_PROP
```

Boolean operators 和 `!` 在 propositional children 上仍保持 `PROP`。

`X/F/G/U` 令 state 变为 `NON_PROP`。

当前 MacroATLAS fragment 不处理 U，但 automaton 如果复用 ATLAS operator enum，应当将 `U` 明确视为 temporal。

---

## 9.2 NNF automaton

ATLAS 风格 NNF：

> negation 只能直接作用于 atomic proposition。

状态：

```text
ATOM
VALID_NON_ATOM
INVALID
```

转移：

Literal：

```text
p -> ATOM
```

Negation：

```text
!(ATOM) -> VALID_NON_ATOM
!(VALID_NON_ATOM) -> INVALID
!(INVALID) -> INVALID
```

其他合法 unary temporal op：

```text
X/F/G(ATOM or VALID_NON_ATOM) -> VALID_NON_ATOM
X/F/G(INVALID) -> INVALID
```

binary：

如果两个 child 均非 INVALID：

```text
-> VALID_NON_ATOM
```

否则：

```text
-> INVALID
```

accept：

```text
ATOM
VALID_NON_ATOM
```

---

## 9.3 CNF automaton

当前 prototype 的 CNF 定义：

- 只允许 literals、`!`、`|`、`&`；
- negation 只能直接在 atom 上；
- `|` 的下面不能出现 `&`；
- temporal operators 非法。

状态：

```text
ATOM
CLAUSE
CNF
INVALID
```

语义：

```text
ATOM   = atomic proposition
CLAUSE = 合法 clause / no-AND subtree，非 atomic
CNF    = 合法 CNF，且某处出现 AND
INVALID
```

转移：

Literal：

```text
p -> ATOM
```

Neg：

```text
!(ATOM) -> CLAUSE
其他 -> INVALID
```

OR：

```text
|(x,y) -> CLAUSE
iff x,y in {ATOM, CLAUSE}
otherwise INVALID
```

AND：

```text
&(x,y) -> CNF
iff x,y in {ATOM, CLAUSE, CNF}
otherwise INVALID
```

其他 operator：

```text
INVALID
```

accept：

```text
ATOM, CLAUSE, CNF
```

---

## 9.4 DNF automaton

CNF 对偶。

状态：

```text
ATOM
TERM
DNF
INVALID
```

Neg：

```text
!(ATOM) -> TERM
```

AND：

```text
&(x,y) -> TERM
iff x,y in {ATOM, TERM}
```

OR：

```text
|(x,y) -> DNF
iff x,y in {ATOM, TERM, DNF}
```

其他非法。

accept：

```text
ATOM, TERM, DNF
```

---

## 9.5 Required-proposition automaton

对一个固定 proposition：

```text
target
```

状态：

```text
ABSENT
PRESENT
```

Literal：

```text
literal == target ? PRESENT : ABSENT
```

Unary：

```text
state unchanged
```

Binary：

```text
PRESENT iff left == PRESENT or right == PRESENT
```

accept：

```text
PRESENT
```

如果 ATLAS proposition 由 index 表示，则使用 index，不要转换成脆弱字符串比较。

---

# 10. ProductConstraintAutomaton

必须提供组合能力。

若：

```text
A1 with Q1
A2 with Q2
...
Ak with Qk
```

则 product state 是：

```text
(q1, q2, ..., qk)
```

所有 transitions component-wise。

接受条件默认：

```text
all component automata accept
```

但是实现不要预先物化：

\[
Q_1\times\cdots\times Q_k.
\]

只在实际 transition 中 lazy 创建 / intern reachable product states。

建议：

```text
ProductState
    immutable list / tuple of component states
```

并做 hash-consing / interning（如果符合项目风格）。

---

# 11. ConstraintAutomata 单元测试

至少测试：

## NNF

合法：

```text
p
!p
G(!p)
F(p & !q)
```

非法：

```text
!!p
!(G p)
!(p & q)
```

## CNF

合法：

```text
p
!p
p | q
(p | !q) & (r | s)
p & q & r
```

非法：

```text
p | (q & r)
!!p
G(p)
```

## DNF

合法：

```text
p
!p
p & q
(p & !q) | (r & s)
```

非法：

```text
p & (q | r)
!!p
G(p)
```

## Product

例如组合：

```text
NNF × RequiredProp(p)
```

确认：

```text
G(!p)
```

accept，

```text
G(!q)
```

RequiredProp 拒绝，

```text
!(G p)
```

NNF 拒绝。

---

# 12. Fiber 的理论定义

真正安全的 canonicalization 单位不是单纯：

```text
SemanticType
```

而是：

\[
\boxed{
(q_{in},\sigma,\eta,q_{out})
}
\]

其中：

- \(q_{in}\)：unary block 下方 child subtree 的 constraint state；
- \(\sigma\)：整个 unary word 的 semantic type；
- \(\eta\)：word 是否非空；
- \(q_{out}\)：对 \(q_{in}\) 依次应用 unary operators 后得到的 state。

定义：

\[
\mathcal F(q_{in},\sigma,\eta,q_{out})
\]

为所有具有这些相同信息的 unary words。

同一 fiber 中的 word：

1. 对任意 child formula 具有相同 LTL semantic context；
2. 对 constraint automaton 暴露同一个 output state；
3. empty/nonempty 一致；
4. 因此后续 MacroDAG 中可以安全选一个最短代表。

---

# 13. FiberTable 的目标

给定：

```text
ConstraintAutomaton<Q>
maxUnaryLength = B
allowed unary ops subset of {!, X, F, G}
```

预计算所有可达 fiber，并为每一个 fiber 保存：

```text
shortest representative unary word
```

长度相同时选择固定 lexicographic 最小者，以确保 deterministic tests / reproducibility。

建议固定 operator order，例如：

```text
! < X < F < G
```

但如果 ATLAS 已经有稳定 operator order，优先复用，并把顺序写进测试。

---

# 14. FiberTable BFS

对于每一个可能的：

```text
qIn
```

单独做 BFS。

初始 state：

```text
word        = empty
semantic    = ID = (0, ID, false)
constraint  = qIn
nonEmpty    = false
length      = 0
```

从当前 unary word \(w\) 扩展时，**在外层 prefix 一个 operator**：

```text
op + w
```

因为 bottom-up state 对新外层 operator：

```text
qNew = automaton.unaryState(op, qCurrent)
```

semantic state：

```text
semanticNew = normalizer.prefix(op, semanticCurrent)
```

nonEmpty：

```text
true
```

actual representative：

```text
prepend(op, word)
```

直到：

```text
length == B
```

---

# 15. FiberKey

建议不可变类型：

```text
FiberKey<Q> {
    Q qIn;
    SemanticType semanticType;
    boolean nonEmpty;
    Q qOut;
}
```

Table：

```text
Map<FiberKey<Q>, FiberRepresentative>
```

Representative：

```text
FiberRepresentative {
    UnaryWord word;
    int length;
}
```

Table 还应支持：

```text
Optional<FiberRepresentative> get(FiberKey key)

Collection<FiberKey> keys()

int size()

FiberKey replay(qIn, word)
```

`replay` 对测试尤其重要。

---

# 16. FiberTable 最重要的正确性 invariant

对 table 中每一条：

```text
key -> rep
```

都必须通过 replay 验证：

```text
rep.length <= B
normalize(rep.word) == key.semanticType
rep.word.isEmpty() == !key.nonEmpty
runConstraint(qIn, rep.word) == key.qOut
```

注意 `runConstraint` 必须按 word 的真实嵌套方向执行。

例如 word：

```text
[F, X, G]
```

表示：

```text
F(X(G(child)))
```

所以从 qIn 开始：

```text
q1 = G(qIn)
q2 = X(q1)
q3 = F(q2)
qOut = q3
```

也就是从 list 尾部向头部 apply。

---

# 17. FiberTable 的 exhaustive minimality 测试

这是第一阶段最重要的测试。

对：

```text
B <= 7
```

暴力枚举所有：

\[
1+4+\cdots+4^7=21845
\]

个 unary words。

对每一个 `qIn`：

1. brute-force 计算每个 word 的 FiberKey；
2. 对每个 key 找最短 word；
3. 同长度用相同 lexicographic order tie-break；
4. 与 FiberTable BFS 的结果逐项比较。

必须：

```text
exactly equal
```

不能只测试 table size。

这会同时验证：

- word 方向；
- semantic normalizer；
- constraint transition；
- nonEmpty；
- BFS minimality；
- tie-breaking。

---

# 18. 必须加入 semantic-equivalent / constraint-different 测试

用于防止以后开发者错误地把 constraint state 删掉。

例如：

\[
\neg Gp\equiv F\neg p.
\]

对 `p` 为 atomic child：

```text
! G
```

和：

```text
F !
```

semantic type 应相同。

但是在 NNF automaton 下：

```text
!(G p)
```

应该进入 INVALID，

而：

```text
F(!p)
```

应该保持 VALID。

所以测试必须断言：

```text
normalize([!, G]) == normalize([F, !])
```

但：

```text
NNF qOut([!, G], ATOM) != NNF qOut([F, !], ATOM)
```

因此二者必须属于不同 fibers。

这个测试非常重要，因为它体现了 MacroATLAS 与普通 semantic canonicalization 的根本区别。

---

# 19. 第一阶段推荐 package 结构

必须先检查原仓库 package 布局，再决定最终位置。

如果现有结构没有明显更合适的位置，可以考虑类似：

```text
cmu.s3d.ltl.macro
├── unary/
│   ├── UnaryOperator
│   ├── UnaryWord
│   ├── SemanticType
│   ├── TemporalTail
│   └── UnaryNormalizer
│
├── constraint/
│   ├── ConstraintAutomaton
│   ├── ProductConstraintAutomaton
│   ├── PropositionalAutomaton
│   ├── NnfAutomaton
│   ├── CnfAutomaton
│   ├── DnfAutomaton
│   └── RequiredPropositionAutomaton
│
└── fiber/
    ├── FiberKey
    ├── FiberRepresentative
    └── FiberTable
```

但是：

> 若 ATLAS 已经存在 operator enum、LTL node 类型或合适 package，应复用并调整上述布局，不要为了照抄本文件制造重复抽象。

---

# 20. 当前阶段禁止做的事情

为了避免 scope creep，本轮明确不要：

### 不要 1：重写 ATLAS

不重新实现：

- parser；
- trace semantics；
- syntax DAG；
- AlloyMax；
- MaxSAT；
- CLI。

### 不要 2：修改 baseline 行为

原：

```text
CLIKt
```

和普通 ATLAS 运行结果必须保持不变。

三个新模块在本阶段可以完全未接入 solver 主路径。

### 不要 3：实现 MacroDAG

Macro anchor slots、macro edges、repair anchors 属于第二阶段。

### 不要 4：实现 generic rank-2 / rank-3 FO type automaton

此前审计已经表明它在 `B <= 15` 时几乎不产生 quotient，尤其 rank 3 在该范围不产生实用压缩。

理论上它仍是 correctness envelope，但不是当前实现目标。

### 不要 5：处理 binary temporal U

当前 semantic normalizer 仅：

```text
!, X, F, G
```

### 不要 6：开始跑论文实验

本轮只做 correctness / unit tests / integration-preservation tests。

---

# 21. 与 ATLAS 原代码的兼容要求

代码大模型首先运行原项目现有 baseline。

至少记录：

```text
git status
git rev-parse HEAD
mvn test / 原项目实际 build 命令
```

并执行 README 中的一个 sample task。

新增模块后，应再次运行相同 baseline。

要求：

```text
原 ATLAS CLI 可以正常运行；
未启用 MacroATLAS 时结果格式和功能不发生改变。
```

不要为了新模块破坏 Java 8 compatibility，除非原项目实际 pom 已要求更高版本；以仓库实际配置为准。

不要随意升级 AlloyMax / Maven dependency。

---

# 22. 代码质量要求

1. 所有核心类型 immutable。
2. `equals/hashCode` 与逻辑 state 一致。
3. BFS 结果 deterministic。
4. 不能依赖 HashMap iteration order 做 tie-breaking。
5. 对 operator order 显式定义。
6. 所有 public class / public method 写简短说明。
7. 理论 invariant 写在代码注释中，但不要把论文长证明粘进源码。
8. 测试命名应反映数学性质，例如：

```text
normalizationIsIdempotent
canonicalLengthNeverIncreases
dualityIsPreserved
nnfDistinguishesEquivalentSyntax
fiberReplayMatchesKey
fiberBfsMatchesBruteForceUpToLength7
```

---

# 23. 第一阶段完成标准（Definition of Done）

代码大模型不要只说“实现好了”。

必须逐项给出：

## Build

原 ATLAS build 成功。

## Baseline regression

至少一个 README sample 在修改前后均可正常运行。

## UnaryNormalizer

- 所有固定 identity test 通过；
- exhaustive words `length <= 8` invariant test 通过。

## ConstraintAutomata

- NNF 单测通过；
- CNF 单测通过；
- DNF 单测通过；
- propositional-only 单测通过；
- required-proposition 单测通过；
- product automaton 单测通过。

## FiberTable

- replay invariant 对所有 generated fibers 通过；
- exhaustive brute-force minimality comparison 在 `B <= 7` 完全一致；
- NNF semantic-equivalent / syntactic-different regression test 通过。

## No solver modification

当前版本没有改变 ATLAS 主求解行为。

---

# 24. 代码大模型完成后必须输出的报告

请让代码大模型在完成代码后同时输出：

```text
1. 修改/新增的文件列表
2. 每个文件的职责
3. 是否复用了 ATLAS 原有 operator / formula 类型
4. UnaryWord 的方向约定
5. SemanticType 的具体数据结构
6. ConstraintAutomaton API
7. 已实现 automata
8. FiberTable BFS 设计
9. tie-breaking 规则
10. 全部测试及测试结果
11. 原 ATLAS baseline regression 结果
12. 任何与本指引不一致、因源码结构而必须调整的地方
13. 当前仍未完成的 TODO
```

如果代码模型发现本指引与实际 ATLAS 源码存在冲突：

> 不要静默猜测或重写整个项目。

它应优先：

1. 保留理论语义；
2. 适配 ATLAS 现有 abstraction；
3. 在报告中明确写出差异和修改理由。

---

# 25. 后续阶段预告，但当前不要实现

这三个组件正确后，下一阶段才做：

```text
MacroDAG / Anchor extraction
        ↓
Port-based O(b+p) macro kernel
        ↓
Fiber-labelled macro edges
        ↓
identity-sensitive constraint compiler
        ↓
AlloyMax / MaxSAT integration
        ↓
formula reconstruction
```

实验设计将在代码通过后单独制定。

---

# 26. 一句话任务说明

如果需要把本任务压缩成一句给代码大模型的最高层指令：

> **Fork ATLAS v1.0.2，不改变现有 solver 行为；在现有源码结构中实现并严格单测一个 U-free unary semantic normalizer、若干 deterministic bottom-up syntactic-constraint automata，以及在 `(q_in, semantic type, nonempty, q_out)` fibers 中通过 BFS 选择最短确定性代表的 FiberTable。第一阶段不实现 MacroDAG、MaxSAT 改写、generic FO types 或实验。**

---

# 27. 理论上最重要的三个不可违背条件

最后再次强调三个容易被代码模型“优化错”的地方：

### 条件 A

不能只按：

```text
SemanticType
```

合并。

必须保留 constraint profile。

### 条件 B

word 的 operator 顺序必须全项目一致：

```text
[F, X, G]
=
F(X(G(hole)))
```

底向上 replay 时必须：

```text
G -> X -> F
```

### 条件 C

FiberTable 中保存的是：

```text
同一 fiber 内最短 representative
```

而不是普通 semantic canonical word。

原因是普通 semantic canonical word可能改变 syntactic constraint state。

这三点如果实现错，后续 Macro-Kernel theorem 的 correctness 就不再成立。
