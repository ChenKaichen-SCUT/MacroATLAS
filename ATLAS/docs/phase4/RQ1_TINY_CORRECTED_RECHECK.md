# RQ1 冻结的 1,000 个小规模实例：修正后独立 Oracle 复核

本次从 `experiment_artifacts/2026-09-23/archives/rq1-tiny-primary-1000.tar.gz` 读取原先冻结的 1,000 个 U-free `.trace`，逐题核对归档 manifest 中的 SHA-256；没有调用生成器，也没有更换实例。八类各 125 题。修正后的独立 Z3 Oracle 对每题从较小公式规模开始逐层求解，共保存了 2,589 个 SMT-LIB 查询，其中 1,770 个 UNSAT、819 个 SAT。对 repair，先尝试保留唯一指定旧边，再尝试不保留，以完整的“最大保留边数、其次最小公式大小”字典序求最优值。

| 类别 | 实例 | Oracle SAT | Oracle UNSAT | Macro 状态分歧 | Macro SAT 目标分歧 | SAT 见证验证通过（Oracle / Macro） |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| plain | 125 | 109 | 16 | 0 | 0 | 109 / 109 |
| nnf | 125 | 109 | 16 | 0 | 0 | 109 / 109 |
| cnf | 125 | 100 | 25 | 0 | 0 | 100 / 100 |
| dnf | 125 | 100 | 25 | 0 | 0 | 100 / 100 |
| required | 125 | 109 | 16 | 0 | 0 | 109 / 109 |
| no_dag_reuse | 125 | 109 | 16 | 0 | 0 | 109 / 109 |
| global_prop | 125 | 100 | 25 | 0 | 0 | 100 / 100 |
| repair | 125 | 83 | 42 | 0 | 0 | 83 / 83 |
| **总计** | **1,000** | **819** | **181** | **0** | **0** | **819 / 819** |

ATLAS-B 的状态分歧和 SAT 最优目标分歧也均为 0；其 819 个 SAT 输出全部通过修正后的独立 verifier。新 Oracle 的 819 个 SAT 见证同样全部通过。与旧 Oracle 逐题比较，状态变化 0、完整目标变化 0，因此本批次修正后的状态一致率为 **1,000/1,000（100%）**，SAT 最优目标一致率为 **819/819（100%）**。`changes.csv` 只有表头；若将来出现变化，复核脚本会列出实例 ID 和新旧结果。

repair 的 83 个 SAT 实例中，41 题的最优字典序目标为 `(保留旧边 1, 大小 2)`，42 题为 `(保留旧边 0, 大小 3)`；不是只比较公式大小。

关于 Weakening，需要明确区分两个数据集：这 1,000 题的八类中**没有 Weakening 实例**，所以修正前后在本批次没有受该分支影响的题，不能据此声称“1,000 个 Weakening 题无变化”。针对实际 E4 Weakening 约束文本，另做了结构负例：`G(->(&(x0,G(x1)),x1))` 中的 `G(x1)` 是 Imply 的严格后代，但不是它的直接孩子。旧 SMT 编码和旧 verifier 分别给出 SAT / 通过；修正后给出 UNSAT / 拒绝。该控制移除了轨迹，只隔离检查结构约束，结果保存在 `weakening-control.json`。它确认 `childrenOf[n] = n.^(l+r)` 已在新编码和 verifier 中按**全部严格后代**解释。CNF/DNF 复核也对严格后代关系作传递检查。

完整逐题数据和证据位于 `ATLAS/experiment_artifacts/2026-09-26/rq1-tiny-corrected-1000/`：`summary/per-case.csv` 有三方状态、完整目标、验证标记和输入 SHA；`summary/evidence-audit.json` 核对全部 1,000 题的 2,589 条查询顺序、查询哈希和 SAT 见证，异常数为 0。`evidence.tar.gz` 包含每题原输入、旧方法记录及公式、每次查询的压缩 SMT-LIB、Z3 结果和 SAT 见证；`evidence.sha256` 校验归档。原 ATLAS-B/Macro 的 SAT 公式从旧归档读取并由独立 verifier 重验，而不是仅信任旧 `verification=PASSED` 字段。要重新审查保存的证据，先在本目录解压 `evidence.tar.gz`，再运行下述 audit 命令。

复现使用 Python 3 与 `z3-solver 4.14.2`。在仓库根目录使用新的输出目录：

```bash
python3 ATLAS/scripts/phase4/rq1_tiny_corrected_recheck.py prepare --output <新目录>
python3 ATLAS/scripts/phase4/rq1_tiny_corrected_recheck.py run --output <新目录> --workers 8
python3 ATLAS/scripts/phase4/rq1_tiny_evidence_audit.py --campaign <新目录>
python3 ATLAS/scripts/phase4/rq1_weakening_semantics_control.py --output <新目录>/weakening-control.json
```

本结论是对**冻结的 1,000 个小规模 RQ1 实例**的完整重算结果；不替代正在另行开展的 623 个 E4 matched 实例独立最优性认证。
