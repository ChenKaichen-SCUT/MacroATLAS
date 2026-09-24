# RQ2 同 scope CNF 翻译补充实验

此实验在原 RQ2 服务器 `110.41.76.57` 上独立运行；不触碰 `139.159.185.102` 上的 E4/RQ4。原 RQ2 的 623 例数据和结果保持原样。新实验使用已冻结的 E4 matched 输入归档、相同的 `B`、`b`、操作符字母表、约束和轨迹。

`s` 是展开公式大小的上界。ATLAS-B 的模型包含 `#experimentReach <= s`；MacroATLAS 生成恰好 `s` 个互斥 cost Unit，且每个被激活的公式节点占据其展开长度对应的 Unit，因此展开公式大小同样不超过 `s`。两个模型都保留相同的最小展开大小目标；repair 的旧边保留目标在两个模型中都不加入，本实验测量相同硬约束和 size 目标下的编码成本，不测 repair 的词典序求解成本。翻译用 `Rq2Translate.java` 在 AlloyMax 的 CNF 计数回调中停止，不启动 MaxSAT 求解。

从原 RQ2 汇总的 623 例中用固定 SHA-256 顺序预选 200 个不同案例：无约束 80、voting 的 NNF/template 10、robot repair 20、Peterson required 30、weakening `b=2` 30、weakening `b=3` 30。每个案例只分配一个满足 `s <= B` 的 scope，候选点为 5、7、9、11、15。正式 `plan.json` 冻结每个案例的 scope、输入 SHA-256、源码和二进制 SHA-256、E4 来源、CPU 分配与超时。这个样本是分层样本，不能当作全部 623 例的无偏估计。

每个 `算法 × 案例 × scope` 只有一次发射和一次 CNF 翻译机会。控制器重启会跳过已有 `record.json`；若只存在 `started.json`，会记录 `INTERRUPTED_UNRECORDED` 而不自动重试。翻译成功记录 `primaryVars`、总变量 `vars`、总 clauses `backendTotalClauses`、时间、模型哈希；发射失败、翻译失败、超时也分别记录状态。仅双方成功翻译的配对计算 `C_V=Vars_A/Vars_M` 和 `C_C=Clauses_A/Clauses_M`，并始终报告两算法翻译成功数及失败/超时数。

最终 `summary/rq2_same_scope_per_run.csv` 有全部 400 次方法记录；`summary/rq2_same_scope_paper_data.csv` 有 200 个配对案例、scope、来源、双方状态和可用比值；`summary/rq2_same_scope_summary.json` 包含覆盖率、分层结果、RQ2a 的 `B/K` 与可定义的 `activeAnchors/expandedSize` 分布。每个案例对应的模型和 stdout/stderr 留在服务器的 `jobs/` 下，供独立核对。旧 623 例的 RQ2a 全量结果仍见 [`RQ2_RESULTS_2026-09-24.md`](RQ2_RESULTS_2026-09-24.md)。

运行期间在服务器上：

```bash
watch -n 5 'macroatlas-rq2-scope status'
tail -F /srv/macroatlas/experiments/rq2-same-scope-200/logs/controller.log
```

结束后在服务器上：

```bash
macroatlas-rq2-scope summary
ls -lh /srv/macroatlas/experiments/rq2-same-scope-200/summary/
```

`summary` 在全部 400 条一次性记录存在后生成。`state.json` 为 `COMPLETE` 表示收集流程完成；某些翻译超时或出错不等于流程未完成，需结合状态分布和完整配对数解读。
