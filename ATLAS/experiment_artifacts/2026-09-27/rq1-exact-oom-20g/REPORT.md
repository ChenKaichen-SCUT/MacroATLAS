# RQ1：623 个 matched 实例的独立 exact Oracle 结果

使用冻结的 623 个 matched 输入及其各自的 `B`、`b` 和约束，独立 SMT Oracle 按目标值逐层检查。普通任务以最小公式大小为目标；repair 任务先要求保留全部可保留旧边，再最小化公式大小。`UNSAT` 表示在该实例的冻结搜索上界 `B` 内不可满足。`TIMEOUT` 不计入正确性一致。

## 最终结果

| Oracle 结果 | 题数 | 占 623 题 |
| --- | ---: | ---: |
| `OPTIMAL` | 457 | 73.35% |
| `UNSAT`（在 `B` 内） | 32 | 5.14% |
| `TIMEOUT` | 134 | 21.51% |
| `UNKNOWN` | 0 | 0% |
| **已独立判定（`OPTIMAL` + `UNSAT`）** | **489** | **78.49%** |

这次只重跑了此前因 5 GiB 单进程地址空间上限而返回 `SMT_out of memory` 的两题。每题大小 1–4 的 UNSAT 查询和哈希已继承并核验；两个 worker 分别绑定 CPU 2、3，各限 20 GiB 地址空间。单次 Z3 上限仍为 1500 秒，单题新尝试墙钟上限仍为 4500 秒。结果如下：

| 实例 | 原状态 | 新状态 | 最小公式大小 | 见证公式 | 新尝试耗时 |
| --- | --- | --- | ---: | --- | ---: |
| `baseTest/0019.trace` | `UNKNOWN`（大小 5 内存不足） | `OPTIMAL` | 6 | `G(->(F(x0),!(x1)))` | 2508.1 秒 |
| `baseTest/0040.trace` | `UNKNOWN`（大小 5 内存不足） | `OPTIMAL` | 5 | `G(->(x1,G(x0)))` | 1070.9 秒 |

两题并行补跑的实际墙钟约 41 分 51 秒。原五倍时限批次墙钟约 11 小时 45 分钟，但它继承了更早批次的认证结果；两者之和不是从零开始完成 623 题的总成本。

## 与 E4 的 ATLAS-B、MacroATLAS 对照

| E4 算法 | `SAT` | `UNSAT` | `TIMEOUT` | `ERROR` | 有确定输出且与 Oracle 状态及完整目标一致 | 有确定输出但分歧 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ATLAS-B | 343 | 3 | 263 | 14 | 346 | 0 |
| MacroATLAS | 384 | 9 | 230 | 0 | 393 | 0 |

两种算法给出确定结果的题目都落在 Oracle 已判定的 489 题中，并且状态及完整目标值均一致。两者共同给出一致结果的题目为 331；仅 MacroATLAS 给出确定结果的已判定题为 62，仅 ATLAS-B 给出确定结果的为 15，两者都没有确定结果但 Oracle 已判定的为 81。上述数字只说明已获得独立判定的范围；不能把 134 道 Oracle 超时题算作已验证正确。

134 道未判定题全部属于 `plain` 类，最终原因均为单次 `SMT_timeout`（1500 秒），没有单题总墙钟超时。按 benchmark family 分布：`increasingNumVariables` 39、`5to10Traces` 33、`moreDetailedTest` 29、`disjunctedExistence` 19、`baseTest` 7、`equal` 7。

## 数据与核验

- [`summary/final-623-core.csv`](summary/final-623-core.csv)：推荐直接用于论文制表的 623 行宽表。每题列出 Oracle 状态、最优公式大小；repair 题另列最优保留旧边数；还包含公式、各算法状态/目标/耗时以及每题 Oracle 的实际尝试次数。
- [`summary/timeout-134.csv`](summary/timeout-134.csv)：从上述宽表筛出的全部 134 道未认证超时题。
- [`summary/final-size-checks.csv`](summary/final-size-checks.csv)：最终 623 题的 3285 条逐规模检查结果、耗时、原因和查询哈希。
- [`summary/actual-attempts.csv`](summary/actual-attempts.csv) 与 [`summary/attempt-size-checks.csv`](summary/attempt-size-checks.csv)：五轮批次中 827 次实际尝试及其 4515 条逐规模检查；继承而未重新执行的整题不重复计作尝试。
- [`summary/campaigns.csv`](summary/campaigns.csv)：五轮批次的时限、内存上限、实际尝试数、继承数和结束状态。
- [`summary/per-case-623-comparison.csv`](summary/per-case-623-comparison.csv)：逐题输入标识、family、`B`、`b`、Oracle 状态与目标、公式、耗时、两算法状态与目标、比较结果及证据批次。134 道超时题也可从此表直接筛选。
- [`summary/merged-623.csv`](summary/merged-623.csv) 与 [`summary/summary.json`](summary/summary.json)：补跑控制器生成的原始合并结果及汇总。
- [`summary/baseTest-0019-result.json`](summary/baseTest-0019-result.json) 与 [`summary/baseTest-0040-result.json`](summary/baseTest-0040-result.json)：两题逐规模结果及查询 SHA-256。

旧五倍时限批次的 623 个结果和本次补跑的 2 个结果均通过 `rq1_exact_audit.py` 结构审计，分别为 `623/623` 和 `2/2`，无坏记录；合并 CSV 经核对包含 623 个唯一实例，状态计数与 `summary.json` 一致。审计会重新检查输入、保存的 SMT-LIB 查询哈希以及 SAT 见证的独立轨迹语义；它**不重新求解**每个保存的 UNSAT 查询。因此 `OPTIMAL` 的支持是逐层保存的 Z3 UNSAT/SAT 求解记录和见证，而非另一个证明检查器验证的 UNSAT 证明对象。

宽表的 `oracleResultAttemptWallSec` 是最终结果所在尝试的耗时，`oracleKnownAttemptsWallSec` 是所有有结果记录的实际尝试耗时之和；17 次中断尝试没有可靠的完整墙钟，未计入后者。继承而未重新执行的整题不会重复计数。

完整可重放 SMT-LIB 查询及见证目前仍在服务器 `/srv/macroatlas-rq1-exact/rq1-exact-623-20260926-5x/jobs` 与 `/srv/macroatlas-rq1-exact/rq1-exact-623-20260927-oom-20g/jobs`。依照本次只保留表格的要求，仓库和本地备份没有包含这些大型查询文件；删除服务器后，上述求解记录与哈希仍可分析，但不能仅凭表格重放 UNSAT 求解或重新核验原始见证文件。
