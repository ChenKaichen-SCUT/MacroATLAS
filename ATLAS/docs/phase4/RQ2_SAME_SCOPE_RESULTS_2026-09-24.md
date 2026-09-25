# RQ2 同 scope 编码补充实验结果（2026-09-24）

**更新：**本文件记录的是先前 200 题的分层样本。现已在不重复这 200 题的条件下完成全部 623 题；论文应优先使用[全量同范围结果](RQ2_FULL_623_RESULTS_2026-09-25.md)，本文件保留作为历史阶段性记录。

按 [`RQ2.txt`](../../../RQ2.txt) 和[预定协议](RQ2_SAME_SCOPE_PROTOCOL.md)，在原 RQ2 服务器 `110.41.76.57` 上从已冻结的 623 个 E4 matched 案例中选取 **200 个不同案例**，每例固定一个展开公式大小上界 `s∈{5,7,9,11,15}`。ATLAS-B 与 MacroATLAS 各生成同一案例、同一 `B,b`、操作符、约束、轨迹和 `s` 下的模型，**只翻译到 CNF 计数回调，不运行 MaxSAT**。源码提交为 `a834e398d2371acace198b4a16c84426a6eaa6da`；每个“方法 × 案例 × scope”只尝试一次，共 **400/400 条记录**，活动状态 `COMPLETE`。两方法模型的 Alloy atom universe 不要求相同，但展开公式大小均受 `s` 约束。

## RQ2b：固定 scope 的后端编码结果

`C_V = Vars_ATLAS-B / Vars_Macro`，`C_C = Clauses_ATLAS-B / Clauses_Macro`；**大于 1** 表示 Macro 的对应 CNF 指标更小。仅对双方都完成翻译的 176 对计算比值：

| 指标 | 176 对的逐例比值中位数 | Macro 更小的配对数 |
| --- | ---: | ---: |
| 后端总变量 `C_V` | **1.421×** | **117/176**（66.5%） |
| 后端总 clause `C_C` | **2.175×** | **168/176**（95.5%） |

把逐例中位比值取倒数，约对应 Macro 变量数为 ATLAS-B 的 70.4%、clause 数为 46.0%；这**不是**把全部案例的变量或 clause 加总后求比。AlloyMax 回调只可靠提供总变量与总 clause 数，未分别给出 hard/soft clause 数。本结果测量编码规模，不测 MaxSAT 求解时间、成功率或最终学习公式。

| 分层组 | 案例 | 双方翻译成功 | `C_V` 中位 | `C_C` 中位 | Macro 变量更少 | Macro clause 更少 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 无约束 `q=1` | 80 | 75 | 0.917 | 1.454 | 29/75 | 75/75 |
| voting NNF/template | 10 | 10 | 2.822 | 3.756 | 10/10 | 10/10 |
| robot repair | 20 | 20 | 9.517 | 13.517 | 20/20 | 20/20 |
| Peterson required | 30 | 30 | 11.305 | 12.864 | 30/30 | 30/30 |
| weakening，`b=2` | 30 | 21 | 1.275 | 1.828 | 17/21 | 18/21 |
| weakening，`b=3` | 30 | 20 | 1.161 | 1.695 | 11/20 | 15/20 |

因此“Macro 总变量总能压缩”并不成立：无约束组中位 `C_V<1`，Macro 在 46/75 个完整无约束配对中变量反而更多。clause 的降低更稳定，但 weakening 组也有 **8/41** 个完整配对的 Macro clause 更多。Peterson/robot 的收益很大，而 weakening 的收益小且不稳定；约束种类比一个总体中位数更能解释结果。

| 固定 scope `s` | 案例 | ATLAS-B 翻译成功 | Macro 翻译成功 | 双方完成配对 | 配对 `C_V` 中位 | 配对 `C_C` 中位 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 5 | 100 | 91 | 98 | 91 | 1.278 | 1.851 |
| 7 | 27 | 25 | 27 | 25 | 1.018 | 1.400 |
| 9 | 33 | 24 | 33 | 24 | 1.118 | 1.716 |
| 11 | 22 | 20 | 22 | 20 | 1.533 | 2.373 |
| 15 | 18 | 16 | 18 | 16 | 2.417 | 3.843 |

同一案例没有在多个 scope 上重复测量；各行的案例构成不同，不能把此表读成压缩比随 `s` 增长的趋势。

## 翻译覆盖率与缺失

| 方法 | 成功翻译 | 超时（180 秒） | 翻译错误 |
| --- | ---: | ---: | ---: |
| ATLAS-B | **176/200** | 21 | 3 |
| MacroATLAS | **198/200** | 2 | 0 |

ATLAS-B 成功的 176 例，Macro 全部也成功；另有 **22 例仅 Macro 成功**（21 例 ATLAS-B 超时、1 例 ATLAS-B 错误）。剩余 2 例中 ATLAS-B 出错且 Macro 超时；没有只由 ATLAS-B 完成翻译的例子。ATLAS-B 的 3 个错误都来自 Alloy 的 `Translation capacity exceeded`，而非被误记成 UNSAT。24 个不完整配对及各自状态保留在逐运行和逐配对表中；不能把只在 176 个完整配对上计算的中位数无条件外推到全部 200 例。翻译覆盖率差异是同 scope 条件下的**编码可处理性**证据，但包含 Macro 的全部表示选择和内部轨迹约简，不能只归因于 unary quotient 一个部件。

## RQ2a 结构预算与结论边界

这 200 例中 **185 例 `K<B`**，`B/K` 的中位数为 **1.636**。从旧 E4 的 150 个 Macro SAT 案例可取得实际 `activeAnchors/expandedSize`，其中位数为 **0.889**。前者是结构预算上界，后者是旧求解轨迹上的实际公式结构；它们与本轮的后端变量和 clause 是不同指标。无约束组即使受预算压缩，变量中位数仍未下降，正说明不能用 `B/K` 直接替代 CNF 大小。

本轮刻意对 constrained 案例增样，且每个案例只选择一个 scope，完整配对还会因翻译超时而进一步偏向较易案例。因此总体 `C_V=1.421` **不是原 623 个 E4 案例的无偏估计**，按 scope 分组的差别也不能解释为“固定同一案例增加 `s` 后的增长曲线”。[原 RQ2 结果](RQ2_RESULTS_2026-09-24.md)测的是 623 个 E4 实际运行中各算法到达的最大模型，576 对有 CNF 指标，中位 `C_V=0.946`、`C_C=1.411`；它与本轮的样本、scope 口径、源码版本均不同，不能把两个中位数之差称为算法改进或纯 scope 效应。本轮解决的是**在相同展开大小上界下，两种完整表示生成的后端 CNF 规模与翻译覆盖率如何不同**。

robot repair 组为保持两方法的模型目标一致，**双方均省略旧边保留的主目标，只保留硬约束和最小展开大小目标**。其显著编码压缩可用于解释结构表示，但不等同于正式 E4 repair 词典序优化模型的全部 CNF 成本。固定 scope 的翻译结果也不直接证明 SAT/UNSAT、解的最优性或运行时间优势。所有案例各只运行一次，没有时间波动的重复估计。

## 数据与复核

- [`rq2_same_scope_paper_data.csv`](../../experiment_artifacts/2026-09-24/rq2-same-scope/summary/rq2_same_scope_paper_data.csv)：200 条配对记录，含 `B,b,K,q,s`、两方法状态、CNF 计数、可用比值和 E4 结构字段。
- [`rq2_same_scope_per_run.csv`](../../experiment_artifacts/2026-09-24/rq2-same-scope/summary/rq2_same_scope_per_run.csv)：400 条逐方法记录，含一次性尝试、模型哈希、翻译状态/时间和错误文本。
- [`analysis.json`](../../experiment_artifacts/2026-09-24/rq2-same-scope/analysis.json)：由独立 [`analyze.py`](../../experiment_artifacts/2026-09-24/rq2-same-scope/analyze.py) 从原始记录重算的总体、分层、scope、成功率和比值统计。
- [`plan.json`](../../experiment_artifacts/2026-09-24/rq2-same-scope/plan.json)、[`rq2_same_scope_summary.json`](../../experiment_artifacts/2026-09-24/rq2-same-scope/summary/rq2_same_scope_summary.json)：冻结选择规则、输入/代码/二进制 SHA-256、CPU/时限和服务器汇总。
- [`rq2-same-scope-records-20260924.tar.gz`](../../experiment_artifacts/2026-09-24/archives/rq2-same-scope-records-20260924.tar.gz)：200 个冻结输入、400 份 `started.json`/`record.json`、400 个模型、翻译 stdout/stderr、计划与日志；[SHA-256](../../experiment_artifacts/2026-09-24/archives/rq2-same-scope-records-20260924.tar.gz.sha256) 已核对。占约 3.2 GiB 的 Kodkod 中间日志与空 WCNF 临时文件留在服务器的原活动目录，未放入仓库归档；论文所用指标均在逐运行记录与翻译输出中。

独立复核逐项验证了：计划与历史 623 例来源哈希一致；200 个案例唯一、`s<=B`；400 次尝试均为第 1 次且 `solverInvoked=false`；输入、模型、翻译输出及两张 CSV 与原始记录一致；失败配对没有被赋予比值。服务器原始目录为 `/srv/macroatlas/experiments/rq2-same-scope-200`，代码提交 `a834e39` 已在仓库 `main` 中。
