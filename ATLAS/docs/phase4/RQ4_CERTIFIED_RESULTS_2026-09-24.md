# RQ4 认证补充实验结果（2026-09-24）

这轮实验按 [`RQ4.txt`](../../../RQ4.txt) 和[认证协议](RQ4_CERTIFIED_PROTOCOL.md)在原 RQ4 服务器 `139.159.185.102` 上完成。预注册的 A/B 组有 18 个案例，ATLAS-B 和 MacroATLAS 各运行一次（36 条）；C 组有 5 个只运行 MacroATLAS 的 profile 案例。**41/41 条记录齐全，没有重复、ERROR 或验证失败**。单次时限 180 秒，源码提交 `1bc3be5c36f454f9448825296a9f1709d676106d`，Java 8；正确性门禁通过 109 项 JVM 测试。A/B 的 28 个 SAT 结果全部达到独立证明的最优大小与二元节点数，8 个 TIMEOUT 保持为未解决。C 组 5 个结果均 SAT 且验证通过。

## A：已知最优大小的一元链

语法只有 `X` 和一个原子命题。正负 lasso 成对地仅在深度 `d` 处取值不同；任何 `X^i x0`（`i<d`）都不能区分对应样本，而 `X^d x0` 可以。因此每个实例的最优大小**确为** `OPT=d+1`。与旧轮中“生成目标深度增加，但学出的公式可能不增长”的系列不同，这里所有已求解结果的实际大小和一元深度都随 `d` 增长。

| 深度 `d` | `OPT=B` | ATLAS-B 状态/秒 | Macro 状态/秒 |
| ---: | ---: | ---: | ---: |
| 4 | 5 | SAT 1.43 | SAT 1.24 |
| 6 | 7 | SAT 2.28 | SAT 1.41 |
| 8 | 9 | SAT 8.51 | SAT 1.94 |
| 10 | 11 | SAT 15.91 | SAT 2.05 |
| 12 | 13 | SAT 91.81 | SAT 2.23 |
| 14 | 15 | TIMEOUT | SAT 2.41 |
| 16 | 17 | TIMEOUT | SAT 3.29 |
| 20 | 21 | TIMEOUT | SAT 3.81 |
| 24 | 25 | TIMEOUT | SAT 4.40 |
| 28 | 29 | TIMEOUT | SAT 4.46 |
| 32 | 33 | TIMEOUT | SAT 6.72 |
| 40 | 41 | TIMEOUT | SAT 8.28 |

ATLAS-B 解出 **5/12**，最大已解最优大小为 13；MacroATLAS 解出 **12/12**，已解至最优大小 41。双方均解出的 5 例里 Macro 全部更快，逐例 `T_ATLAS-B/T_Macro` 的中位数为 **4.38×**。180 秒 PAR-2 分别为 220.00 秒与 3.52 秒。这里可稳妥声称：**在本轮 X-only、`b=0` 的认证一元链上，MacroATLAS 的 180 秒可解范围至少达到大小 41，ATLAS-B 在大小 15 及以后均超时**。因为预注册网格在 41 截止、Macro 尚未超时，不能声称 Macro 的可解前沿恰好是 41，也不能推断渐近复杂度。随着 `d` 增长，轨迹长度和 `B` 也一起增长；这不是只改变 `B`、保持任务其余难度不变的因果实验。

## B：已知二元节点下界的合取

语法只有 `&` 和 `n` 个原子命题；每题使用全部 `2^n` 个单状态赋值，目标是全部变量的合取。每个变量都不可缺少，故至少需要 `n` 个 literal 和 `n-1` 个二元节点；目标合取式达到 `OPT=2n-1`。所有 SAT 结果确实达到该最优值。整个系列 `K=B`，即 Macro 在结构预算上**没有压缩空间**。

| `n` | `b=n-1` | `OPT=B=K` | ATLAS-B 状态/秒 | Macro 状态/秒 |
| ---: | ---: | ---: | ---: | ---: |
| 2 | 1 | 3 | SAT 0.65 | SAT 0.71 |
| 3 | 2 | 5 | SAT 0.82 | SAT 0.89 |
| 4 | 3 | 7 | SAT 0.96 | SAT 1.13 |
| 5 | 4 | 9 | SAT 1.46 | SAT 3.39 |
| 6 | 5 | 11 | SAT 2.53 | SAT 12.20 |
| 7 | 6 | 13 | SAT 17.12 | TIMEOUT |

ATLAS-B 解出 **6/6**，MacroATLAS 解出 **5/6**；双方解出的 5 例里 Macro 全部更慢，中位 `T_ATLAS-B/T_Macro=0.85×`。180 秒 PAR-2 为 3.92 秒与 63.05 秒。`n=6` 时 Macro 用时约为 ATLAS-B 的 4.83 倍；`n=7` 时 Macro 超时而 ATLAS-B 在 17.12 秒解出。这是算法适用边界的直接证据：当真实二元分支增多且 `K=B` 时，Macro 的 catalog、状态和端口开销可能压过其收益。`n` 增长时 AP 数、样本数、`B` 和 `b` 同时增长，因此不能把时间变化单独归因于 `b`，也不能从六个点推出一般性能定律。

## C：仅改变辅助 profile 状态数

五题的 trace 集、目标 `X(X(x0))`、`B=17`、`b=0` 和 X-only 语法均相同，实际学得大小恒为 3。实验用一个**所有状态都接受**的辅助自动机记录深度模 `q`，只对特定标记的实验输入跳过通常的语言等价合并，从而让实际 `q` 等于预设的 1、2、4、8、16。这个设计隔离了 profile 表示开销；它不是自然约束分布，也不表示生产默认路径会保留无意义状态。ATLAS-B 忽略该标记，故本组没有重复运行五个语义相同的 ATLAS-B 基线。

| 实际 `q` | fiber catalog | 后端变量 | 后端 clause | encoding 秒 | solver 秒 | 总秒 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 4 | 4,387 | 8,758 | 0.0031 | 0.574 | 0.820 |
| 2 | 10 | 4,918 | 10,082 | 0.0034 | 0.618 | 0.879 |
| 4 | 28 | 7,024 | 15,832 | 0.0039 | 0.731 | 0.995 |
| 8 | 88 | 14,545 | 37,517 | 0.0052 | 0.909 | 1.224 |
| 16 | 288 | 41,379 | 115,893 | 0.0079 | 1.321 | 1.569 |

从 `q=1` 到 `q=16`，fiber catalog 增加 **72×**，后端变量约 **9.43×**、clause 约 **13.23×**；总时间约 **1.91×**。这说明即使可行语言与最优公式完全不变，保留更多 profile 状态也会显著扩大 Macro 的内部编码。`encodingSec` 只是模型构造阶段，不能把它当成完整的翻译或求解时间。五题各只运行一次，时间曲线没有重复测量的方差估计。

## 对 RQ4 的更新结论与材料

这轮认证实验填补了[前两轮报告](RQ4_RESULTS_2026-09-24.md)中的两个缺口：一元链的**实际最优大小**现已证明并观察到从 5 增至 41；二元分支对照也不再退化为大小 1。结论同时更有边界：Macro 在小 `b` 的长一元链上显著扩大可解范围，却在 `K=B` 的二元合取系列落后；profile 状态数的独立压力测试量化了内部编码的增长。不能概括为“Macro 总比 ATLAS-B 快”，也不能把这批合成任务外推至全部 E4 题目。

复核材料均已归档：

- [`rq4c_paper_data.csv`](../../experiment_artifacts/2026-09-24/rq4-certified/combined/rq4c_paper_data.csv)：41 条逐运行记录，含状态、耗时、结构、编码大小和来源。
- [`rq4_paper_data.csv`](../../experiment_artifacts/2026-09-24/rq4-certified/ab/rq4_paper_data.csv) 与 [`rq4c_profile_data.csv`](../../experiment_artifacts/2026-09-24/rq4-certified/profile/rq4c_profile_data.csv)：A/B 和 C 的分组数据；两个 `plan.json`、门禁、原始 merged CSV 与审计文件在同目录。
- [`analysis.json`](../../experiment_artifacts/2026-09-24/rq4-certified/analysis.json)：由独立的 [`analyze.py`](../../experiment_artifacts/2026-09-24/rq4-certified/analyze.py) 校验计划、原始/派生记录、证书和 SHA-256 后生成的分组统计。
- [`rq4-certified-records-20260924.tar.gz`](../../experiment_artifacts/2026-09-24/archives/rq4-certified-records-20260924.tar.gz)：23 个输入案例、41 个原始运行工件、计划、日志和汇总的完整轻量归档；[SHA-256](../../experiment_artifacts/2026-09-24/archives/rq4-certified-records-20260924.tar.gz.sha256) 已核对。约 101 MB 的相同源码 bundle 留在服务器两活动目录，仓库已有 `1bc3be5` 对应源码及 [bundle 校验值](../../experiment_artifacts/2026-09-24/rq4-certified/source-bundle.sha256)。

独立校验还确认两个活动 `strictOnce=true`、`repeats=1`，原始记录与汇总逐条匹配，41 个 `task × algorithm × repeat` 键唯一；A/B 的 28 个已求解证书均通过，8 个超时不计作正确性一致或 UNSAT。
