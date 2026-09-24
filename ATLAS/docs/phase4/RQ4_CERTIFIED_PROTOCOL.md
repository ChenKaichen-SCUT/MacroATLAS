# RQ4.txt 补充实验协议：可证明结构与隔离的 profile 轴

此实验在原 RQ4 服务器 `139.159.185.102` 上单独运行。旧 `rq4-scale-once`
活动和 110 上的 `rq4-followup-once` 均冻结；新案例一律使用 `rq4c_` ID。
18 个 A/B 案例各运行 ATLAS-B、MacroATLAS 一次，5 个 C 案例只运行
MacroATLAS 一次，共 **41 次**。两个活动顺序执行，互不竞争 CPU。

| 组 | 参数 | 输入、语法与独立证书 | 可回答的问题 |
| --- | --- | --- | --- |
| A：Unary size | `d=4,6,8,10,12,14,16,20,24,28,32,40`，`B=d+1,b=0` | 仅允许 `X` 与一个 literal；16 对正负 lasso 除第 `d` 个位置外逐对完全相同。每个公式只能是 `X^i x0`，`i<d` 不可分，`i=d` 可分，故 `OPT=d+1`。 | 实际最优大小增加时的完成率与耗时前沿；网格固定，不按结果增删任务。 |
| B：Binary branching | `n=2..7`，`B=2n-1,b=n-1` | 仅允许 `&` 和 `n` 个 literal；全部 `2^n` 个单状态赋值。合取中每个变量 essential，至少 `n` 个 literal 和 `n-1` 个二元节点；合取式达到该界。 | 避免退化为大小 1，观察 `b=1..6` 的完成率和耗时。 |
| C：中性 profile | `m=1,2,4,8,16`，固定 `B=17,b=0`、trace、目标和 `X` 语法 | 附加自动机记录 `X` 深度模 `m`，**所有状态都接受**，所以可行公式和最优值不变。一个精确的 Alloy 注释只让 Macro 实验路径保留这些状态；ATLAS-B 忽略它。 | 单独测 `q` 对 fiber catalog、变量/clause、编码时间和求解时间的影响。 |

组 B 按文件建议使用 `2^n` 个样本，因而 `n` 增长时 AP、trace 数、`B`
和 `b` 也一起增加。即使得到趋势，也不能把全部耗时变化因果归于 `b`。
它是一条有正确性证书的**联合扩展曲线**。组 A 的 trace 长度随 `d` 增长，
所以同理不是“只改变 `B`”的纯实验，但可证明真实最优大小增长。

组 C 是刻意的**profile 表示开销压力测试**。普通语言等价最小化会把一个
全接受自动机的 `m` 个状态全部合并为 1；若不显式跳过此最小化，表面
`m=1..16` 并不会改变生产算法中的 `q`。这里仅对精确标记
`// RQ4_NEUTRAL_PROFILE_STATES=m`、且 `X`-only、`b=0`、`B>=m` 的任务
保留辅助状态；其余任务沿用原最小化。这个 C 结果不能表述为自然语法约束的
平均代价，也不是生产默认路径会保留无意义状态的证据。C 的 ATLAS-B
输入忽略这条注释，故不做五次语义相同的基线重复运行；比较的是 Macro
自身同一语义任务下的 profile 开销。

生成器和输入侧单元测试先验证配对证书与布尔真值表。服务器用 Java 8
的 `correctness_gate.py` 对冻结提交运行 Maven、Python、原版/修复/同域
回归后才创建正式计划。两活动都采用 180 秒时限、`--strict-once`、
`repeats=1`，7 个不重叠 CPU sibling 组、每 worker 10 GiB 和 4 GiB
Java heap；C 只有 5 个 worker。`TIMEOUT/ERROR` 是未解决，不得视作
UNSAT 或证明最优。A/B 任一已完成结果与独立证书矛盾会让审计失败。

自动生成文件：A/B 的 `rq4_paper_data.csv`、`rq4_pairs.csv`、
`rq4c_ab_audit.json`，C 的 `rq4c_profile_data.csv`、
`rq4c_profile_summary.json`，以及两组的 `rq4c_paper_data.csv`、
`rq4c_summary.json`。逐运行表保留状态、壁钟时间、`B,b,K,q`、实际
公式大小/一元深度/二元节点数、fiber 数、后端变量与 clause、
`encodingSec`、`solverSec`、验证结果和耗时截断。原始输入、计划、
正确性门禁、每次运行工件及日志留在服务器活动目录。

服务器上的控制命令：

```bash
macroatlas-rq4-certified run
macroatlas-rq4-certified status
macroatlas-rq4-certified watch
macroatlas-rq4-certified tail
macroatlas-rq4-certified summary
```
