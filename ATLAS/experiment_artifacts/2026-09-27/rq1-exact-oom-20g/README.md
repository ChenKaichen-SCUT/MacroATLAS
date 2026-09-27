# RQ1 exact 623：两道内存不足实例的定向补跑

源批次 `/srv/macroatlas-rq1-exact/rq1-exact-623-20260926-5x` 已完成 623 题，其中 `baseTest/0019.trace` 和 `baseTest/0040.trace` 在公式大小 1–4 获得 UNSAT 记录，大小 5 时 Z3 返回 `out of memory`。这两题的旧结果保持不变。新批次只含这两题，冻结计划见 [plan.json](plan.json)。

新批次位于服务器 `116.205.139.162` 的 `/srv/macroatlas-rq1-exact/rq1-exact-623-20260927-oom-20g`。使用两个分别绑定 CPU 2、3 的 worker，每个进程虚拟地址空间上限 20 GiB，单次 Z3 检查上限 1500 秒，单题新尝试总墙钟上限 4500 秒。已复制并逐一核验两题大小 1–4 的 UNSAT 查询哈希；从大小 5 续跑，避免重新求解已证层级。控制脚本为 [`rq1_exact_oom_retry.py`](../../../scripts/phase4/rq1_exact_oom_retry.py)。服务为 `macroatlas-rq1-exact-oom-20g.service`。

在该服务器上实时查看进度：

```bash
watch -n 5 '/srv/macroatlas-rq1-exact/venv/bin/python /srv/macroatlas-rq1-exact/rq1-exact-623-20260927-oom-20g/code/rq1_exact_oom_retry.py status --campaign /srv/macroatlas-rq1-exact/rq1-exact-623-20260927-oom-20g'
journalctl -u macroatlas-rq1-exact-oom-20g.service -f
```

两题均已完成并获得 `OPTIMAL`：`baseTest/0019.trace` 最小大小 6，`baseTest/0040.trace` 最小大小 5。新批次的 `summary/summary.json` 汇总 623 题更新后的状态，`summary/merged-623.csv` 逐题标明所用证据批次；此前 621 题的证据继续引用旧批次，没有重新运行。完整统计与核验范围见 [REPORT.md](REPORT.md)。
