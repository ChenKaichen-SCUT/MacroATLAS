# MacroATLAS Prototype 第四阶段实验与评测指引
## 目标：冻结 Phase 3，实现可复现、公平、可用于论文的完整实验评测

> 起点：Phase 3 已完成真实 MacroDAG 搜索、repair 优化、OFF/AUTO/FORCE、解码与独立验证。
>
> Phase 4 原则：**不再扩功能，除非某项实验所需的 instrumentation / ablation flag 缺失。**
>
> 本阶段要回答：
> 1. MacroATLAS 在其声明支持的 fragment 上是否保持 exact correctness / optimality？
> 2. 是否真正减少搜索编码？
> 3. 是否提升端到端 scalability？
> 4. 性能收益来自哪些组件？
> 5. 性能如何随 B、b、p、trace 数量和 unary-chain 长度变化？
> 6. 在哪些实例上无收益或变慢？

---

# 0. 先冻结代码

开始实验前运行：

```bash
git status --short
git rev-parse HEAD
git log -5 --oneline --decorate
mvn -B clean verify
```

要求工作区 clean、89 项测试全部通过、243 个普通差分任务和 50 个 repair 差分任务保持通过、OFF 默认路径不变。

创建实验 tag：

```bash
git tag macroatlas-phase3-frozen
```

若正式实验期间发现 correctness bug：
1. 停止实验；
2. 修复；
3. 全测试重跑；
4. 新建 tag；
5. 此前所有性能结果作废重跑。

---

# 1. 固定实验环境

正式环境建议：

```text
OS: Ubuntu 22.04 Linux amd64
Solver: OpenWBOWeighted
Java: 固定一个版本
CPU: 记录完整型号
physical/logical cores
RAM
git commit
OpenWBO binary checksum
AlloyMax jar checksum
```

Baseline 与 MacroATLAS 必须使用同一机器、solver、JVM、timeout。

主实验统一：

```text
-s OpenWBOWeighted
-T 180
```

Docker 可用于复现，但正式 timing 建议 native Linux amd64。

---

# 2. 单任务独立进程

正式 benchmark：

```text
one task = one JVM process
```

避免跨任务 JIT/cache 污染，也方便测 peak RSS。

每次运行使用唯一目录：

```text
results/<commit>/<machine>/<timestamp>/
```

每个 task 保存：

```text
stdout.csv
stderr.log
metadata.json
verification.json
timing.json
analysis.json
```

---

# 3. 重复次数

Correctness / solved count：1 次 deterministic run。

Runtime：
- 全集至少 1 次；
- common-solved 或分层抽样集至少 3 次；
- runtime 用 median-of-3。

若完整 3 次代价过高，必须在报告中说明。

---

# 4. 统一状态分类

```text
SAT
UNSAT
TIMEOUT
UNSUPPORTED
FALLBACK
ERROR
VERIFICATION_FAILED
```

AUTO 模式必须额外记录：

```text
solverMode = MACRO / ORIGINAL
fallbackReason
```

Fallback 不能算 Macro solve。

---

# 5. RQ0：Correctness gate

在大规模实验前重新运行：

- 全部 unit/integration tests；
- 243 ordinary differential tasks；
- 50 repair differential tasks；
- CLI tests；
- verifier。

要求：

```text
0 verification failures
0 objective mismatches
0 unexpected FORCE fallbacks
```

任何 mismatch 都停止 Phase 4。

---

# 6. RQ1：Benchmark applicability / coverage

对官方 `benchmark/` 只运行 analyzer，不求解。

每个 task 输出：

```text
task
benchmark_family
supported
reason
nodeBudget
operatorSet
binaryBudgetUsed
protectedCount
recognizedFeatures
```

分类至少：

```text
SUPPORTED_MACRO
UNSUPPORTED_U
UNSUPPORTED_RAW_CONSTRAINT
UNSUPPORTED_OBJECTIVE
UNSUPPORTED_TEMPLATE
OTHER
```

按 family 报：

```text
total
supported
coverage %
fallback reasons
```

不能只报告被支持的子集而不说明筛选比例。

---

# 7. 公平比较：必须同搜索域

MacroATLAS 有 binary budget b，因此主性能实验必须比较：

```text
ATLAS-B(b)
vs
MacroATLAS-B(b)
```

双方必须使用：
- 同一 node bound B；
- 同一 AP；
- 同一 operator alphabet；
- 同一 binary-node budget b；
- 同一 traces；
- 同一 constraints；
- 同一 objectives。

如果原 ATLAS 没有 binary-count 开关，允许 Phase 4 加一个**只用于 baseline 公平比较**的 Alloy 约束：

```text
#BinaryNodes <= b
```

该约束必须通过 tiny reference enumeration 验证等价。

禁止把：

```text
MacroATLAS b=2
```

直接与 unrestricted ATLAS runtime 比较后作为主要 speedup claim。

---

# 8. 第二类比较：AUTO deployment

另做：

```text
Original ATLAS
vs
MacroATLAS --macro auto
```

覆盖整个 workload。

AUTO 中：
- supported -> Macro；
- unsupported -> original fallback。

此实验回答 drop-in deployment 效果，但不得与 matched-domain 结果混为一谈。

---

# 9. U-free matched variants

若原 task operator set 含 `U`，主 matched 实验需要生成 U-free variant：

```text
remove U from allowed operator set
```

同时对 baseline 和 Macro 使用同一个 variant。

生成到：

```text
generated/matched_u_free/
```

保留原 task，不覆盖。

---

# 10. RQ2：Encoding reduction

每个 matched task记录 Baseline 与 Macro：

```text
B
b
p
K=min(B,p+3b+2)
search node universe
anchor slot budget
constraint state count
fiber catalog size
ports
active anchors
active macro edges
expanded size
```

若 backend 可获得，再记录：

```text
Boolean vars
hard clauses
soft clauses
generated model bytes
```

核心指标：

\[
R_{nodes}=B/K
\]

若可得：

\[
R_{vars}=Vars_{ATLAS}/Vars_{Macro}
\]

\[
R_{clauses}=Clauses_{ATLAS}/Clauses_{Macro}
\]

若 backend 不暴露 CNF counts，不要伪造；用可获取的 model/atom/relation metrics 替代并说明 limitation。

---

# 11. RQ3：End-to-end scalability

主指标：

```text
solved within timeout
wall-clock
PAR-2
peak RSS
common-solved speedup
timeouts
errors
```

一个 task 只有：

```text
solver returns result
AND FinalSolutionVerifier == PASSED
```

才算 solved。

Verification failure 单独记 ERROR。

---

# 12. PAR-2

timeout=180s 时：

```text
solved -> actual runtime
timeout/error -> 360s
```

同时报告：
- solved count；
- PAR-2；
- common-solved median runtime。

不要删除 timeout 后只平均 solved runtime。

---

# 13. Speedup

对 common-solved：

\[
speedup_i=T_{baseline,i}/T_{macro,i}
\]

报告：
- median；
- geometric mean；
- 25/75 percentile。

不要只报告最大 speedup。

---

# 14. Peak memory

Linux 可用：

```bash
/usr/bin/time -v
```

记录：

```text
Maximum resident set size
```

Macro 的 analysis / fiber build / encode / solve / verify 全包含在同一端到端进程。

---

# 15. 主图

至少生成：

1. Cactus runtime；
2. baseline-vs-Macro log-log scatter；
3. encoding reduction distribution；
4. speedup vs \(B/K\)；
5. ablation；
6. synthetic scaling vs unary length；
7. overhead breakdown。

---

# 16. RQ4：Ablation

安全可实现的配置优先：

```text
A0 Original matched-domain ATLAS
A1 Macro structure with minimal/no semantic quotient（仅在语义正确可实现时）
A2 + unary semantic normalization
A3 + constraint-aware fibers
A4 + identity-specialized skeleton constraints
```

如果 A1 会导致大改或 correctness 不清楚，不要强行实现。

可以改为：

```text
Original
Macro on unconstrained tasks
Macro + constraint-aware profiles
Full Macro
```

每个 ablation 必须独立正确。

指标：
- encoding size；
- solver time；
- total time；
- solved；
- fiber count。

---

# 17. RQ5：Parameter sensitivity

系统改变：

```text
B
b
p
#AP
#positive traces
#negative traces
trace length
unary-chain pressure
```

推荐：

```text
B ∈ {5,7,9,11,15,21,31}
b ∈ {0,1,2,3,4}
p ∈ {0,1,2,4,8}
#traces ∈ {4,8,16,32,64}
trace length ∈ {4,8,16,32}
```

若某参数后全部 timeout，可以按预先定义 stopping rule停止更大规模。

---

# 18. RQ6：Synthetic favorable stress

构造：

```text
small b
long unary chains
```

示例 target：

\[
X^k p
\]

\[
FX^kGp
\]

\[
X^{k_1}p \land FX^{k_2}q
\]

\[
G(FX^{k_1}p 	o X^{k_2}q)
\]

只用当前支持 fragment。

目标是验证理论预测的：

\[
b\ll B
\]

区域。

---

# 19. Synthetic unfavorable/control

必须同时构造：

```text
binary-heavy
little unary chaining
K≈B
```

例如 balanced Boolean trees。

用于检验 Macro overhead 和适用边界，避免 cherry-picking。

---

# 20. Synthetic generator

输入：

```text
seed
target formula
B
b
AP
trace count
trace length
```

输出：
- `.trace`；
- manifest；
- target；
- seed。

positive / negative labels用独立 lasso evaluator生成，不调用 solver normalization逻辑。

---

# 21. 官方 benchmark 自动发现

不要在脚本硬编码“论文有多少个实例”。

从 frozen repo 自动枚举：

```text
benchmark/
```

记录：
- relative path；
- family；
- task count。

保存 `benchmark_results/` 仅作 provenance/reference。

正式 performance 必须在当前机器重新跑 Original ATLAS。

---

# 22. Baseline reproduction

先跑：

```text
--macro off
-s OpenWBOWeighted
-T 180
```

复现当前机器的 Original ATLAS baseline。

检查：
- solved趋势合理；
- 输出格式；
- 无系统性异常。

不要直接把官方历史 runtime 与当前 Macro runtime 比。

---

# 23. supported task list

由 RQ1 analyzer 自动生成：

```text
supported_tasks.txt
```

matched-domain主实验只能基于该列表自动运行，不人工挑 task。

---

# 24. Correctness comparison in benchmark

每个 Macro SAT：

```text
verification == PASSED
```

双方都 solved 时比较 objective tuple。

若 mismatch：
- 标记 correctness failure；
- 停止相关性能解释；
- 调查原因。

不要求最终 formula string 相同。

---

# 25. Repair 指标

repair比较：

```text
kept old-edge count
expanded size
```

按 lexicographic tuple比较。

不能只比 formula size。

---

# 26. Coverage 与 performance 分表

至少：

## Table A — Coverage

```text
family
tasks
Macro-supported
coverage
main unsupported reason
```

## Table B — Matched performance

```text
variant
solved
PAR-2
median common runtime
geo mean speedup
peak RSS
```

## Table C — Encoding

```text
variant
structural nodes
vars
clauses
model size
```

## Table D — Repair

```text
solved
kept-edge optimality
size optimality
runtime
```

---

# 27. AUTO deployment 单独报告

整套 workload：

```text
Original ATLAS
MacroATLAS AUTO
```

报告：
- total solved；
- total wall time/PAR-2；
- macro-used count；
- fallback count；
- fallback reasons。

---

# 28. Overhead breakdown

用 Phase 3 timing：

```text
analysis
fiberBuild
encodingBuild
solver
decode
verify
```

报告 median fraction / stacked summary。

回答：

> solver节省是否被 Macro overhead抵消？

---

# 29. Fiber statistics

记录：

```text
catalog size
reachable q states
semantic types
fibers selected by solution
mean representative length
max representative length
```

把理论 quotient 与实际 benchmark联系起来。

---

# 30. Kernel tightness

记录：

\[
K_{bound}=p+3b+2
\]

和：

```text
activeAnchorCount
expandedSize
```

报告：

\[
activeAnchors/K_{bound}
\]

以及：

\[
activeAnchors/expandedSize.
\]

---

# 31. 重要关联图

画：

```text
x = B/K
y = speedup
```

或：

```text
x = 1-K/B
y = log(speedup)
```

直接检验：

> structural compression越强，性能收益是否越明显？

如果没有相关性，也必须如实报告。

---

# 32. 第二个关联图

```text
x = fiber catalog size
y = encoding time / solver time
```

观察 profile catalog开销。

---

# 33. Failure analysis

单独分析：

```text
Macro >2x slower
Macro timeout, baseline solves
baseline timeout, Macro solves
K≈B
fiber catalog unusually large
repair cases
```

输出：

```text
docs/phase4/FAILURE_ANALYSIS.md
```

不要只讨论成功案例。

---

# 34. Coverage failure analysis

统计 unsupported原因：

```text
U
unknown raw Alloy
unsupported objective
repair semantics not covered
other
```

这些可自然形成 Future Work。

---

# 35. 统计处理

Runtime：
- median；
- geometric mean；
- bootstrap 95% CI（可选但推荐）。

Paired common-solved 可用 Wilcoxon signed-rank，但 effect size更重要。

Solved outcome同时报：

```text
both solve
only baseline
only Macro
neither
```

---

# 36. 实验噪声控制

- 不同时并行跑多个 solver进程；
- 尽量关闭重负载；
- 固定 CPU governor（若可）；
- 重复 run时固定 seed随机打乱 task顺序；
- 保存 permutation；
- baseline与Macro相同处理 JVM warm-up。

---

# 37. Memory limit

如设置：

```text
16GB
```

双方完全相同。

OOM记：

```text
ERROR/OOM
```

不等同 timeout。

---

# 38. Reproduction manifest

每批实验生成：

```json
{
  "commit": "...",
  "machine": "...",
  "cpu": "...",
  "ram": "...",
  "os": "...",
  "java": "...",
  "solver": "OpenWBOWeighted",
  "timeoutSec": 180,
  "benchmarkRoot": "...",
  "taskListHash": "...",
  "commandTemplate": "..."
}
```

---

# 39. 统一 result schema

```text
task
family
variant
repeat
status
solverMode
fallbackReason
B
b
p
K
qStates
fiberCount
activeAnchors
expandedSize
objectivePrimary
objectiveSecondary
analysisSec
fiberSec
encodingSec
solverSec
decodeSec
verifySec
totalSec
peakRssKb
verification
```

若可获取：

```text
vars
hardClauses
softClauses
```

---

# 40. 自动 validation

`validate_results.py` 检查：

- expected run齐全；
- commit一致；
- 无 duplicate；
- Macro SAT全 PASSED；
- 无 objective mismatch；
- status合法；
- fallbackReason 与 solverMode一致；
- OFF 不应出现 Macro path metadata。

---

# 41. 图表不可手工改数据

全部：

```text
raw CSV
-> script
-> table / plot
```

一键重建。

不允许手工复制 Excel 后改数字。

---

# 42. Phase 4 执行顺序

## E0
Freeze + environment manifest。

## E1
RQ0 correctness gate。

## E2
Official benchmark analyzer coverage。

## E3
Original baseline reproduction。

## E4
Matched supported-domain run。

## E5
AUTO whole-workload run。

## E6
Encoding metrics。

## E7
Ablation。

## E8
Synthetic favorable/unfavorable scaling。

## E9
Statistics + plots + failure analysis。

严格按顺序。

---

# 43. Definition of Done

必须全部完成：

### Reproducibility
- frozen commit；
- environment manifest；
- deterministic task lists；
- scripts；
- raw results保留。

### Correctness
- RQ0全通过；
- Macro SAT verifier无失败；
- matched solved objective无 mismatch。

### Coverage
- 整个官方 benchmark analyzer分类完成；
- coverage按family报告。

### Baseline
- same-machine Original ATLAS重跑。

### Matched-domain
- 同 B/b/operators/constraints/objectives；
- solved/PAR-2/runtime/memory；
-统一 timeout。

### Encoding
- structural counts；
- backend counts若可获得；
- reduction ratios。

### Ablation
- 至少一个安全且可解释的 ablation suite。

### Synthetic
- favorable；
- unfavorable/control；
- parameter scaling。

### Analysis
- 自动 plots/tables；
- failure analysis；
- limitations。

### Claims
- bounded-b明确；
- U-free明确；
- supported constraints明确；
- AUTO fallback明确。

---

# 44. 最终文档结构

建议：

```text
scripts/phase4/
results/raw/
results/processed/
docs/phase4/
  EXPERIMENT_PROTOCOL.md
  ENVIRONMENT.md
  COVERAGE.md
  CORRECTNESS.md
  PERFORMANCE.md
  ABLATION.md
  SYNTHETIC.md
  FAILURE_ANALYSIS.md
  LIMITATIONS.md
```

大体量 raw logs可以外部 archive，但需保留下载说明和 checksum。

---

# 45. Phase 4 完成后必须汇报

1. frozen commit；
2. machine/OS/CPU/RAM；
3. Java / OpenWBO；
4. 官方 benchmark实际 family/task数；
5. Macro supported数与 coverage；
6. fallback原因；
7. Original baseline solved/PAR-2；
8. Macro matched solved/PAR-2；
9. common-solved median / geo speedup；
10. peak memory；
11. encoding reduction；
12. repair结果；
13. ablation；
14. synthetic scaling；
15. failure cases；
16. verification failures（应为0）；
17. objective mismatches（应为0）；
18. raw data位置；
19. scripts；
20. 目前证据支持哪些论文 claim。

---

# 46. 给代码大模型的一句话最高层指令

> **冻结 Phase 3，不再扩 solver capability；在同一 Linux amd64 / OpenWBOWeighted / 180s 环境中，先重跑 Original ATLAS baseline，再对 MacroATLAS 当前严格支持的 U-free fragment构造完全同域的 matched comparison（同 B、同 b、同 operators、同 constraints/objectives），测量 correctness、coverage、encoding size、solved count、PAR-2、wall-clock、peak memory和 overhead；同时做 AUTO whole-workload deployment、safe ablation、参数敏感性以及 small-b/long-unary 与 binary-heavy control synthetic suites。所有 Macro SAT result必须 verifier PASSED，objective mismatch视为 correctness failure；bounded-b 结果不得冒充 unrestricted optimum。所有结果由自动脚本从 raw data生成，正式性能实验期间不再修改算法。**
