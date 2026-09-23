# AUTO 语义修复与 Weakening consequent `b=3` 定向复跑

日期：2026-09-23。代码提交 `ce9ed6f122056d0f3822b95d9bafd520167f453f`。原 1/4 实验与问题分析见 [QUARTER_V2_RESULTS.md](QUARTER_V2_RESULTS.md)。服务器在独立工作树 `/srv/macroatlas/repo-v3` 上通过正确性门禁：104 JUnit、243 ordinary differential、50 repair differential、80 matched reference、18 Python 测试。原 v1/v2 实验目录和代码工作树均未改写。

## 修复与复跑范围

AUTO 对已知 Weakening consequent 模板在 `b<3` 时直接回退 Original，因为模板至少需要 Imply、And、Or 三个二元节点。其他受限 Macro 若求得 UNSAT，AUTO 保存 `bounded-attempt.json` 并调用 Original；只有经独立验证的受限 SAT 才直接作为原问题的 SAT。CLI 与 Phase 4 `ExperimentMain` 均执行此规则。

目标清单为 [weakening-consequent-quarter-tasks.txt](weakening-consequent-quarter-tasks.txt)，逐项等于 v2 1/4 计划抽中的 9 个 Weakening consequent 任务。`campaign.py --target-tasks` 把此清单和 SHA-256 `e11caa6bf199829c9a784cbbfe855c52a1664b45e1cb75147a728f41d3a99b82` 登记到计划，只调度这些任务。新 `b=3` matched 输入的 SHA-256 与 v2 的同名 `b=2` matched 输入逐项一致。两个定向批次沿用原服务器、Java 8u462、OpenWBOWeighted、180 秒、5 个 CPU 隔离 worker、每 worker 16 GiB 和 JVM 堆 4 GiB；每个任务/算法只运行一次。

| 批次 | 服务器目录 | 任务/运行数 | 结果 |
| --- | --- | ---: | --- |
| AUTO 修复，原样输入 `b=2` | `/srv/macroatlas/experiments/phase4-auto-fix-consequent-9-b2` | 9/9 | 4 FALLBACK/SAT，5 TIMEOUT；4 个 SAT 的独立轨迹验证均通过 |
| matched consequent `b=3` | `/srv/macroatlas/experiments/phase4-matched-consequent-9-b3` | 9 题、18 次 | MacroATLAS 9 SAT；ATLAS-B 4 SAT、5 TIMEOUT |

两个批次均为 `COMPLETE`，`validate_results.py` 分别校验 9/9 与 18/18 个结果，没有 `VERIFICATION_FAILED` 或已解匹配目标值冲突。`b=3` 下 MacroATLAS 的 9 个 SAT 公式大小均为 7；双方共同 SAT 的 4 题目标值同为 7。该 4 题的 ATLAS-B/MacroATLAS 耗时比中位数为 0.280，说明共同解出的任务上 MacroATLAS 仍较慢；但 MacroATLAS 还在限时内解出了 ATLAS-B 超时的 5 题。该定向 9 题的 PAR-2 为 ATLAS-B 205.93 秒、MacroATLAS 37.95 秒。此结果只描述 Weakening consequent 的 `b=3` 搜索域，不能与旧 `b=2` 的 9 个结构性 UNSAT 直接合并为同一搜索域。

复用 v2 AUTO 批次中未受影响的 147 条记录，并用新的 9 条记录逐任务替换后，**派生汇总**为 156 题：106 SAT（90 个成功回退、16 个直接 Macro）、46 TIMEOUT、4 ERROR、0 UNSAT，PAR-2 136.52 秒。旧 Original E3 是 102 SAT、50 TIMEOUT、4 ERROR、PAR-2 147.55 秒。派生汇总显示相对 Original 多 4 个 SAT；它明确混合了 v2 和修复后两个代码提交的保留记录，不冒充一个新的单批次测量，也不改变原始 CSV。重新跑全部 156 题才能得到单提交 AUTO 完整批次。

原始 CSV SHA-256：AUTO 修复 `617077969cfb1633d8e4c2787936fb5dfbc183f3e32649623fd6d3167702de04`；matched `b=3` `d31046ec4693ee871fcaa7621568114248b27b2de3de17d551fa4d6d736a2ccb`。归档：

- `/srv/macroatlas/archives/phase4-auto-fix-consequent-9-b2-20260923T051856Z.tar.gz`，SHA-256 `c2508f8ced1ebfeebc41881f71338563ca75138cd0f6e8560e5be02380daa0a7`。
- `/srv/macroatlas/archives/phase4-matched-consequent-9-b3-20260923T051857Z.tar.gz`，SHA-256 `98723c8f8ede95b6040df9a45288b4ac830e203c866de468184271a90d2b031c`。

## 服务器命令

这两个批次已完成。`run` 用于中断后的断点续跑；完成状态下不会重算已登记的任务。只在 AUTO 批次完成或停止后启动 matched 批次，避免 CPU 竞争。

```bash
ssh root@110.41.76.57 'macroatlas-auto-fix9 run'
ssh root@110.41.76.57 'macroatlas-auto-fix9 status'
ssh -t root@110.41.76.57 'macroatlas-auto-fix9 tail'
ssh root@110.41.76.57 'macroatlas-auto-fix9 summary'
ssh root@110.41.76.57 'macroatlas-auto-fix9 stop'

ssh root@110.41.76.57 'macroatlas-weak-b3 run'
ssh root@110.41.76.57 'macroatlas-weak-b3 status'
ssh -t root@110.41.76.57 'macroatlas-weak-b3 tail'
ssh root@110.41.76.57 'macroatlas-weak-b3 summary'
ssh root@110.41.76.57 'macroatlas-weak-b3 stop'

ssh root@110.41.76.57 'cat /srv/macroatlas/experiments/phase4-matched-consequent-9-b3/e4-matched/merged/processed/comparison.json'
```
