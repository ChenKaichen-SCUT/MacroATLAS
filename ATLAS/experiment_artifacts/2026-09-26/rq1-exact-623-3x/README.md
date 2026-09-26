# RQ1 / 623 题独立最优值：三倍时限续跑

上一轮 `/srv/macroatlas-rq1-exact/rq1-exact-623-20260926-long` 已完成 623/623：442 `OPTIMAL`、16 `UNSAT`、165 `TIMEOUT`。使用修正后的独立 verifier 对全部 623 条结果和已保存的 SMT 查询作只读审计，`bad=[]`；458 条已认证结果继承到新计划，仅重试 165 条超时实例。完整实例 ID、输入 SHA、旧耗时和停止位置见 [`initial-timeouts.csv`](initial-timeouts.csv)。

| 超时实例的 benchmark family | 数量 |
| --- | ---: |
| 5to10Traces | 45 |
| baseTest | 13 |
| disjunctedExistence | 19 |
| equal | 9 |
| increasingNumVariables | 39 |
| moreDetailedTest | 40 |
| **合计** | **165** |

165 题的实际约束类别全部是 `plain`，旧原因全部是 `SMT_timeout`，没有 Weakening 实例。最后一次检查停在精确大小 4、5、6、7、8 的题数依次为 2、6、98、57、2；旧每题耗时中位数约 485.7 秒。此前的 E4 运行中，这 165 题的 MacroATLAS 全部超时，ATLAS-B 有 159 题超时、6 题出错，因此它们仍需独立最优值认证。

新计划沿用原 623 个输入的 SHA、`B`、`b`、最大编码大小 18、Z3 4.14.1 和每 worker 5 GiB 地址空间上限。**单次 SMT 检查由 300 秒增至 900 秒，每题总墙钟由 900 秒增至 2700 秒**。源代码提交为 `e0afbb64b59b4fbe184af16b38dadf055285912e`，运行脚本和 Oracle 被复制进新计划并记录哈希。系统服务使用 10 个互不重叠的 CPU 2–11。新计划与继承元数据分别见 [`plan.json`](plan.json)、[`continuation.json`](continuation.json)。

服务器 `116.205.139.162` 上的运行目录是 `/srv/macroatlas-rq1-exact/rq1-exact-623-20260926-3x`，服务名为 `macroatlas-rq1-exact-623-3x.service`。实时查看：

```bash
watch -n 5 '/srv/macroatlas-rq1-exact/venv/bin/python /srv/macroatlas-rq1-exact/rq1-exact-623-20260926-3x/code/rq1_exact_campaign.py status --campaign /srv/macroatlas-rq1-exact/rq1-exact-623-20260926-3x'
tail -n 30 -F /srv/macroatlas-rq1-exact/rq1-exact-623-20260926-3x/controller.log
systemctl status macroatlas-rq1-exact-623-3x.service --no-pager
```

完成后汇总并使用修正后的 verifier 复核：

```bash
/srv/macroatlas-rq1-exact/venv/bin/python /srv/macroatlas-rq1-exact/rq1-exact-623-20260926-3x/code/rq1_exact_campaign.py summary --campaign /srv/macroatlas-rq1-exact/rq1-exact-623-20260926-3x
/srv/macroatlas-rq1-exact/venv/bin/python /srv/macroatlas-rq1-exact/repo-bundle/ATLAS/scripts/phase4/rq1_exact_audit.py --campaign /srv/macroatlas-rq1-exact/rq1-exact-623-20260926-3x
```

`TIMEOUT` 或 `UNKNOWN` 仍表示未认证，不计入与 ATLAS-B / MacroATLAS 的正确性一致；三倍时限不保证全部 165 题都能得到最优值。
