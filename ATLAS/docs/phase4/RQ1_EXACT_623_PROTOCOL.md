# RQ1：623 个 matched 实例的独立最优值验证

此实验与 E4 的 ATLAS-B、MacroATLAS 求解结果分离。验证程序直接把输入轨迹和约束翻译成新的 Z3 有界 DAG 编码，不调用两种被比较的求解器、Alloy 模型或它们输出的公式。E4 结果只在验证结束后用于比较。每个案例只安排一次验证尝试。

## 输入与搜索空间

`rq1_exact_campaign.py plan` 从 RQ2 的 623 行完整表冻结 matched `.trace` 输入，并逐一校验 SHA-256、`B`、`b` 和约束类别。输入分为 485 个无自定义约束、10 个 voting、30 个 Peterson、20 个 robot repair 和两组各 39 个 weakening 案例。编码枚举**精确 DAG 节点数** `s=1,2,...`；每个节点的孩子编号必须更小，每个节点必须从根可达，AP 节点至多各出现一次，二元节点数不超过 `b`。逐条 lasso 的 `X/F/G/!/&/|/->` 语义在 Z3 中定义；`U` 已在 matched 输入预处理时移除。自定义约束只接受冻结输入中已校验哈希的模板。

常规案例从 `s=1` 开始，保存每层的完整 SMT-LIB 查询和 Z3 结果。较小的所有 `s` 为 UNSAT，当前 `s` 为 SAT，且由独立的 Python 轨迹与结构检查器验收见证时，报告 `OPTIMAL`。只有 `1..B` 全部 UNSAT 时才报告 `UNSAT`。本批次默认最多编码到 `s=18`；若 `B>18` 且未找到 SAT，则只报告 `UNKNOWN`，绝不把大小截断误报成不可满足。

Repair 采用完整字典序目标。其第一目标是最大化保留的旧边数；两种冻结模板分别有 4 和 5 条不同的旧边。验证程序在每层直接要求**所有**旧边保留，因而任何可行见证都达到第一目标的绝对上界；随后证明此条件下更小的所有 DAG 大小不可行。若没有找到保留全部旧边的公式，则不得据此给出原 repair 问题的最优值，结果是 `UNKNOWN`。结果文件同时保留旧边数和 DAG 大小。

## 证据、资源限制与解释

每个 `jobs/<case-id>/size_XXX/` 包含 `query.smt2.gz`、`record.json`，SAT 层还包含 `witness.json`。`record.json` 存储查询 SHA-256、Z3 版本、求解状态及耗时；`result.json` 汇集逐层记录、目标值、公式和总耗时。可用 `gzip -dc query.smt2.gz | z3 -in` 独立重放某层。SMT-LIB 与求解记录是**可重放的求解证据**，不是形式证明对象；UNSAT 的可信度仍依赖 Z3 及编码正确性。编码另外与已有 125 个无约束小案例的穷举 oracle 对照，并在主要约束类别的试点案例上逐层检查。

第一批每案例墙钟上限 300 秒，每次 Z3 检查最多 120 秒。应用户要求，第二批分别放宽到 **900 秒**和 **300 秒**。单进程地址空间上限均为 5 GiB。超时、内存耗尽、进程中断、编码范围未覆盖或求解器返回 unknown 均不算已证明。并行 worker 固定到不同 vCPU。

放宽时先停止第一批调度，对其已完成的 `OPTIMAL/UNSAT` 逐项审计并复制完整证据到新批次；`rq1_exact_continue.py` 同时生成继承来源和第一批尝试清单。第二批运行器自动跳过已证明案例，仅重试第一批超时或被中断的案例、并处理尚未启动的案例。第一批原始目录保留，因此重试是有明确来源的**第二次尝试**，绝不覆盖首次超时记录。第二批结束时 `per-case.csv` 会标记 `previousStatus` 和 `evidenceSource`。

完成后运行 `rq1_exact_campaign.py summary --campaign <目录>`，得到 `summary/per-case.csv`、`summary/summary.json` 和 `summary/REPORT.md`。只有 `OPTIMAL` 或 `UNSAT` 才能与 E4 结果构成正确性对照；TIMEOUT、UNKNOWN、ERROR、缺失及 E4 原算法超时都列为未解决，不能以双方结果相同代替最优性证明。

`rq1_exact_audit.py --campaign <目录>` 对冻结计划与代码哈希、输入哈希、每层查询哈希、状态连续性和 SAT 见证执行只读审计。它**不会**把记录中的 UNSAT 当作形式证明：要重放 UNSAT 查询，仍需用 Z3 或其他兼容的 SMT 求解器重新执行保存的 SMT-LIB。
