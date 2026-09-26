# RQ1 / 623 题独立最优值：五倍时限续跑

三倍时限续跑停止时为 468/623：442 `OPTIMAL`、21 `UNSAT`、5 `TIMEOUT`。使用修正后的独立 verifier 对已有查询、SAT 见证和证书再次审计后，新的五倍时限计划继承 **463 个已认证实例**，只重试其余 **160 个**。五倍时限运行目录为 `/srv/macroatlas-rq1-exact/rq1-exact-623-20260926-5x`，服务为 `macroatlas-rq1-exact-623-5x.service`。

三倍时限新增的 5 个超时均属于 `plain`，原因都是 `SMT_timeout`；余下 160 题也全部属于 `plain`。完整实例 ID、输入 SHA 和三倍时限下的状态见 [`retry-160.csv`](retry-160.csv)。其中 5 题已超时、10 题在切换时正在求解而被中断、145 题尚未开始；中断的题没有被错误地计为认证结果。

| 仍需重试的 benchmark family | 数量 |
| --- | ---: |
| 5to10Traces | 41 |
| baseTest | 12 |
| disjunctedExistence | 19 |
| equal | 9 |
| increasingNumVariables | 39 |
| moreDetailedTest | 40 |
| **合计** | **160** |

五倍时限均相对于最初的 300 秒 / 900 秒：**每次 Z3 检查 1500 秒，每题总墙钟 4500 秒**。其他条件保持原 623 题冻结输入 SHA、各题 `B` 和 `b`、最大编码大小 18、Z3 4.14.1 和每 worker 5 GiB 地址空间上限。10 个 worker 分别绑定 CPU 2–11，不互相竞争。脚本与 Oracle 源自提交 `e0afbb64b59b4fbe184af16b38dadf055285912e`；新计划的源码和输入哈希见 [`plan.json`](plan.json)，继承证书的来源见 [`continuation.json`](continuation.json)。

实时查看进度和日志：

```bash
watch -n 5 '/srv/macroatlas-rq1-exact/venv/bin/python /srv/macroatlas-rq1-exact/rq1-exact-623-20260926-5x/code/rq1_exact_campaign.py status --campaign /srv/macroatlas-rq1-exact/rq1-exact-623-20260926-5x'
tail -n 30 -F /srv/macroatlas-rq1-exact/rq1-exact-623-20260926-5x/controller.log
systemctl status macroatlas-rq1-exact-623-5x.service --no-pager
```

服务完成后会自动写 `summary/per-case.csv`、`summary/summary.json` 和 `summary/REPORT.md`。也可手动汇总并复核：

```bash
/srv/macroatlas-rq1-exact/venv/bin/python /srv/macroatlas-rq1-exact/rq1-exact-623-20260926-5x/code/rq1_exact_campaign.py summary --campaign /srv/macroatlas-rq1-exact/rq1-exact-623-20260926-5x
/srv/macroatlas-rq1-exact/venv/bin/python /srv/macroatlas-rq1-exact/repo-bundle/ATLAS/scripts/phase4/rq1_exact_audit.py --campaign /srv/macroatlas-rq1-exact/rq1-exact-623-20260926-5x
```

五倍时限仍不能保证所有难题获得最优值；`TIMEOUT` / `UNKNOWN` 不计入认证数量或正确性一致率。
