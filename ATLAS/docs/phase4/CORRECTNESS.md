# Phase 4 正确性门禁

Phase 3 冻结门禁重新通过 89 项 JUnit 测试、243 普通差分、50 repair 差分以及默认 CLI 回归。新增 experimental baseline 使用 80 个固定种子（20260923）任务，对比原 concrete-DAG encoding、Macro、独立 TinyReferenceEnumerator：33 SAT、47 UNSAT、0 objective mismatch。

另有三命题合取测试：仅允许 AND 时，确实需要两个 binary nodes；b=0/1 无解，b=2 在 B=5 得到最优解。用于避免 binary-bound 编码只在容易的 literal 任务上被验证。

Python tests 覆盖独立 lasso 标签、确定性生成、PAR-2 保留失败、目标/UNSAT 不一致立即拒绝、统一 schema、超时终止并回收整个 JVM/native 进程组。

端到端预检在 repair 样例上发现并拦截了一次 ATLAS-B 验证失败。分析后修复了实验适配层两个问题：

- 原始 generator 的 X successor 未限制到当前 trace 的长度；对较短 trace，会读到范围外的自由 valuation。ATLAS-B 增加范围限制；新增不同有限表示但表示同一无限 trace、正负标签冲突的测试，必须返回 UNSAT。
- `minsome experimentReach` 对派生闭包表达式没有正确实现预期最小化。改成显式 `ExperimentCost.used = experimentReach`，最小化该 relation；repair fixture 必须恰好两节点、保留一条 old edge。

两项回归均覆盖 SAT4JMax/OpenWBOWeighted；新增 Until verifier 的 eventuality 测试。原 Original 求解器不修改，这些适配会在比较中明示。修复前 matched 资源预检已作废，重新执行的文件使用 `resource-pilot-matched-v2`。5 个 CLI fixture、10 次 matched 运行在修复后全部 SAT、验证通过、目标一致。

Python validator 另验证缺失计划任务、丢失验证文件、CSV 与逐任务 JSON 不一致时拒绝分析。

AUTO 额外完成两个官方任务、共四次短窗口运行：已解任务明确标为 FALLBACK/TRACE_PASSED；超时任务保留 fallbackUsed 与原因，状态保持 TIMEOUT。结果见 `preflight/phase4-auto-smoke.csv`，只用于路径与日志验证。

服务器正式运行前执行 `scripts/phase4/correctness_gate.py`。它要求干净 commit，运行 Maven 全回归与 Python tests，核对 differential 计数，然后输出带 commit/JVM/依赖 checksum 的证书。`run.py` 的正式模式验证证书，拒绝不一致版本；pilot 明确不签发正式结论。

`validate_results.py` 检查所有 expected runs、重复、commit、合法状态、宏 SAT 验证、fallback 分类、同域 B/b/p/objective 和结果 tuple。验证失败或双方都 solved 时结果不同，立即视为 correctness failure，而非较慢的性能点。

完整最终构建摘要位于本目录 preflight 下的 Java 8/21 文件：各 94 项 JUnit 测试通过，另 7 项 Python 测试通过。最终资源 pilot 的所有返回 SAT 均通过相应验证；时间超时没有被误写成 UNSAT。
