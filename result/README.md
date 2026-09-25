# RQ1–RQ4 画图与制表数据

这里的五张 UTF-8 CSV 均为**逐运行长表**：一行是一个案例的一种算法。`task`（RQ1 小案例为 `caseId`）加 `algorithm` 可唯一定位一行。空单元格表示原始实验没有该值，例如超时题的最优公式大小、oracle 未生成的 CNF 指标；不要将其填成零。所有案例每种算法只运行一次。

| 文件 | 案例 / 运行行数 | 用途与关键列 |
| --- | ---: | --- |
| `RQ1_small_1000.csv` | 1,000 / 3,000 | 八类小案例；`family`、`algorithm`（Oracle、ATLAS-B、MacroATLAS）、`status`、字典序目标、`verification`、结构验证与耗时 |
| `RQ1_official_623.csv` | 623 / 1,246 | 官方 matched 大案例；双算法的确定状态、目标、验证与耗时；`bothDecisive`、`pairStatusAgreement`、`pairObjectiveAgreement` 便于画一致性表 |
| `RQ2_translation_623.csv` | 623 / 1,246 | 相同输入和固定展开上界 `scope=s` 的两种表示；`status`、`vars`、`backendTotalClauses`、翻译时间、`B/b/K/qStates`、约束类型及完整配对比值 `C_V`、`C_C` |
| `RQ3_E4_623.csv` | 623 / 1,246 | E4 matched 端到端；`batch`、`category`、`status`、`totalSec`、`par2Sec`、`peakRssMiB`、目标、验证、CNF 规模及阶段耗时 |
| `RQ4_certified_23.csv` | 23 / 41 | 认证案例；`instanceClass` / `instanceClassZh` 指出三类实例，另有结构轴、可证最优值、实得结构、状态、耗时、CNF 与 profile 指标 |

RQ4 三类 `instanceClass` 分别为 `unary_structure_growth`（一元结构增长，12 题、24 行）、`binary_branch_growth`（二元分支增长，6 题、12 行）和 `constraint_profile`（constraint-profile，5 题、5 行）。最后一类只运行 MacroATLAS，因为 ATLAS-B 忽略人为保留辅助状态的实验标记；CSV 没有虚构 ATLAS-B 行。RQ4 的早期 30 题探索轮和 13 题补充轮未放入此表，主文档的可扩展性结论以这 23 个可认证案例为准。

RQ2 使用**最新完整的 623 题同范围 CNF 翻译**，其中包括先前的 200 题和新增的 423 题；主文档 [`RQ1-RQ4_实验设计与结果.md`](../RQ1-RQ4_实验设计与结果.md) 的 RQ2 段落目前仍描述较早的 200 题阶段，最新结论见 [`RQ2_FULL_623_RESULTS_2026-09-25.md`](../ATLAS/docs/phase4/RQ2_FULL_623_RESULTS_2026-09-25.md)。这张表**没有运行 MaxSAT**，`TRANSLATED_ONLY` 是 CNF 翻译成功，不是 SAT。`C_V=Vars_ATLAS-B/Vars_Macro`、`C_C=Clauses_ATLAS-B/Clauses_Macro`，只在 `pairedTranslated=True` 时有效；为方便按算法筛选，配对比值出现在双方两行中，计算案例中位数时应先按 `task` 去重。`campaign` 区分原 200 题和后 423 题，不是算法版本。

RQ1 官方大案例与 RQ3 的 E4 是**同一批求解运行的两种整理口径**，不可相加计作独立重复。RQ3 的 `par2Sec` 在 SAT/UNSAT 时等于实测 `totalSec`，在 TIMEOUT/ERROR 时按 180 秒时限记 360 秒；`peakRssMiB` 为原始 `peakRssKb/1024`。RQ4 使用各行的 `timeoutSec` 按相同规则计算 `par2Sec`。若要比较 RQ4 的加速比，只在同一认证系列、同一 `task` 且双方均完成的 A/B 对中计算；C 系列没有双算法配对。

来源：RQ1 和 RQ3 取自 [`2026-09-23`](../ATLAS/experiment_artifacts/2026-09-23/)；RQ2 取自 [`rq2-full-623/summary`](../ATLAS/experiment_artifacts/2026-09-25/rq2-full-623/summary/)；RQ4 取自 [`rq4-certified/combined`](../ATLAS/experiment_artifacts/2026-09-24/rq4-certified/combined/)。运行 `python3 result/build.py` 可从这些归档重新生成五张表；脚本检查案例数、唯一键、一次运行标记和 RQ1/RQ2/RQ3 的共同题目集合，不启动实验。
