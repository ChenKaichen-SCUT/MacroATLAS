# RQ2 全部 623 题的同范围 CNF 翻译协议

本轮在 `110.41.76.57` 上复用已完成的 200 题同范围实验，仅对冻结 E4 matched 清单中剩余的 **423 题**发射模型并翻译 CNF。两方法逐题使用相同输入、`B`、`b`、运算符、约束与展开公式大小上界 `s`，各尝试一次；翻译在 CNF 计数回调中停止，**不启动 MaxSAT**。早期按两算法各自实际搜索最大模型采集的 623 题指标不参与新汇总。

旧 200 题的 `s` 原样保留。新增 423 题按稳定 SHA-256 顺序分配候选循环 `5,7,5,9,5,11,5,15`，选不超过 `B` 的候选值；旧抽样因 `B<5` 没有覆盖的 84 题均有 `B=3`，本轮使用 `s=3`。计划冻结每题输入哈希、参数、scope、代码/二进制哈希及旧 200 题计划哈希。旧计划和原始记录保持只读；新增案例使用独立活动目录。两方法可有不同 Alloy atom universe，但展开大小上界相同。repair 两边均只保留相同硬约束与最小展开大小目标，省略旧边保留主目标，因此此实验不代表正式 E4 repair 词典序求解的全部成本。

服务器已安装 `macroatlas-rq2-full` 和 `macroatlas-rq2-full.service` 后，用下面命令启动一次：

```bash
systemctl start macroatlas-rq2-full.service
```

实时查看完整 623 题进度、两方法状态及日志：

```bash
watch -n 5 'macroatlas-rq2-full status'
journalctl -u macroatlas-rq2-full.service -f --no-pager
```

系统服务的 `Restart=no`；控制器在 `record.json` 存在时跳过该运行，只见 `started.json` 而没有最终记录时标记 `INTERRUPTED_UNRECORDED`，**不会自动重试**。故重启服务也不能让一个已发射的“案例 × 算法 × scope”重复运行。进度中的 `XXX/623` 包含旧 200 题，新增活动单独预期 423 题、846 条方法记录；完成状态 `COMPLETE` 代表所有计划记录已落盘，不代表全部翻译成功。

全部完成后，自动生成或手动重算以下文件：

```bash
macroatlas-rq2-full summary
macroatlas-rq2-full report
ls -lh /srv/macroatlas/experiments/rq2-same-scope-full-remaining-423/summary/rq2_full_623_*
```

最终文件在 `/srv/macroatlas/experiments/rq2-same-scope-full-remaining-423/summary/`：`rq2_full_623_paper_data.csv` 有 623 条配对结果，`rq2_full_623_per_run.csv` 有 1246 条逐方法结果，`rq2_full_623_summary.json` 包含总体与分组统计，`RQ2_FULL_623_REPORT.zh-CN.md` 是可引用的中文报告。只有双方翻译成功的配对才计算 `C_V=Vars_ATLAS-B/Vars_Macro` 和 `C_C=Clauses_ATLAS-B/Clauses_Macro`，失败配对留空。报告给出完成数、翻译状态、无约束/受约束及家族分组，并明确完整配对的选择限制。

旧 200 题仍在 `/srv/macroatlas/experiments/rq2-same-scope-200/`，新增 423 题在 `/srv/macroatlas/experiments/rq2-same-scope-full-remaining-423/`。所有原始 `started.json`、`record.json`、模型与 stdout/stderr 保留在各自活动目录。完成后应归档最终 CSV/JSON/报告与新 423 题原始记录、校验来源哈希，再同步回本地与 GitHub。

实验已完成；实际数据与分析见[全量结果报告](RQ2_FULL_623_RESULTS_2026-09-25.md)。
