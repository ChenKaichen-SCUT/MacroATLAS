# 冻结的 1,000 个 RQ1 小规模实例：修正后独立 Oracle 完整复核

从原始归档复制并核对了全部 1,000 个输入 SHA-256；未重新生成实例。独立 Z3 有限 DAG 编码逐规模证明可满足性，SAT 见证与原 ATLAS-B / MacroATLAS 返回的公式都由具体 lasso/约束 verifier 重验。
CNF/DNF 的 `childrenOf[n]` 按 `n.^(l+r)` 的**所有严格后代**检查。修正前后的 Weakening 代码对本批次不适用，因为八类中没有 Weakening 实例。

| family | 题数 | Oracle SAT | Oracle UNSAT | Macro 状态分歧 | Macro SAT 目标分歧 | Oracle SAT 验证 | Macro SAT 验证 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| plain | 125 | 109 | 16 | 0 | 0 | 109 | 109 |
| nnf | 125 | 109 | 16 | 0 | 0 | 109 | 109 |
| cnf | 125 | 100 | 25 | 0 | 0 | 100 | 100 |
| dnf | 125 | 100 | 25 | 0 | 0 | 100 | 100 |
| required | 125 | 109 | 16 | 0 | 0 | 109 | 109 |
| no_dag_reuse | 125 | 109 | 16 | 0 | 0 | 109 | 109 |
| global_prop | 125 | 100 | 25 | 0 | 0 | 100 | 100 |
| repair | 125 | 83 | 42 | 0 | 0 | 83 | 83 |
| TOTAL | 1000 | 819 | 181 | 0 | 0 | 819 | 819 |

ATLAS-B：状态分歧 0，SAT 最优目标分歧 0，SAT 输出独立验证通过 819。
旧 Oracle 与本次重新求解的状态/目标变化：**0**；逐题见 `changes.csv`。
状态一致率：100.0%；SAT 最优目标一致率：100.0%。
每题 SHA、完整字典序目标和三方验证见 `per-case.csv`；每个 Oracle SAT/UNSAT 查询及见证保存在 `../evidence.tar.gz` 的 `jobs/` 中。解压后可用 `rq1_tiny_evidence_audit.py` 重验。

复现：`python3 ATLAS/scripts/phase4/rq1_tiny_corrected_recheck.py prepare --output <新目录>`，然后 `run --output <新目录> --workers 8`。
