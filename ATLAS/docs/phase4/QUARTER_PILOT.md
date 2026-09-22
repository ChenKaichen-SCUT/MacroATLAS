# 原论文 1/4 分层探索实验

本批次用于决定是否继续全量实验，不代替全量结论。旧全量批次及其源码保持原样，
新批次使用独立 checkout `/srv/macroatlas/repo-quarter` 和结果目录
`/srv/macroatlas/experiments/phase4-quarter`。

固定 seed=20260922，不读取既有运行耗时、SAT/TIMEOUT 或历史结果值来选择任务。
从原论文历史表的 **文件名映射**确定 623 题总体，按论文类别比例分配 156 个名额，
再按输入 family 比例分配，使用最大余数法和固定种子打乱。
抽样清单、覆盖情况、输入校验和与源码随 plan 归档；不因运行失败而换题。

| 类别 | 原总体 | 1/4 子集 | U-free 副本可用于 matched |
| --- | ---: | ---: | ---: |
| 无约束 learning | 485 | 121 | 121 |
| Peterson | 30 | 8 | 0 |
| Voting | 10 | 2 | 0 |
| Robot / Repair | 20 | 5 | 0 |
| Weakening | 78 | 20 | 0 |
| 总计 | 623 | 156 | 121 |

- E3: 156 个原样输入运行 Original，一次。
- E4: 121 个被选中的、可支持的 U-free 输入副本，ATLAS-B/Macro 各重复三次，共 726 次。
- E5: 同一批 156 个原样输入，Original/AUTO 各一次，共 312 次。
- 共 1194 次；本批次不运行额外的 ltlsketch 或 synthetic 工作负载。
- 当前原样输入全部回退；constrained 部分没有可用于 Macro 同域比较的任务。
  因此 constrained 只报告 Original/AUTO、回退及覆盖率，不能声称测到了 Macro 的 constrained 加速。
- 180 秒超时、5 workers、每 worker 同一 SMT 组的两个逻辑 CPU、16 GiB 内存上限、4 GiB heap 不变。
- 比较只在同一阶段的同一输入和搜索域内进行，不将 E3 与 E4 直接相除。
- 固定种子的本次 1/4 选择是对应 1/2 选择的子集（有回归检查）；扩展时仍要新建批次并保留选择依据。

## 原批次停止原因与输入诊断

旧批次在 `voting_machine/voting5.trace` 报 `VERIFICATION_FAILED` 并停止。
异常证据是 `NoSuchElementException: Key x8 is missing in the map`：某个原始状态
只有 6 个命题值，而任务要求 10 个。原始输入没有被补零、修复或从抽样中剔除。

新实验入口仍调用原样 Original learner，保留返回的公式、SAT/UNSAT outcome 和求解耗时；
随后检查输入能否作为完整具体轨迹验证。不完整输入记为 `ERROR`、
`verification=INVALID_INPUT`、`InvalidArtifactTraceException`，不计为成功，并保留在
统计分母及 PAR-2 惩罚中。输入错误单独列出，不能归因于算法速度。
有效输入上的公式分类错误、Macro 验证失败或 matched objective mismatch 仍会停止整批运行。
旧记录不追溯改写，新旧版本的结果不混合。

## 已部署命令

```bash
macroatlas stop                 # 停止旧全量批次，保留全部数据
macroatlas-quarter run          # 启动或恢复 1/4；断开 SSH 后继续
macroatlas-quarter status       # 进度和磁盘
macroatlas-quarter tail         # 实时日志；Ctrl-C 仅退出查看
macroatlas-quarter stop         # 暂停 1/4
macroatlas-quarter summary      # 全部完成后校验、分类统计、CSV 与 PDF
macroatlas-quarter backup       # 暂停或完成后备份
```

分类别汇总：`/srv/macroatlas/experiments/phase4-quarter/processed/paper-subset-summary.csv`。
逐阶段完整统计/图：`<campaign>/<phase>/merged/processed/`。
`selection.json`、`selection-counts.csv` 记录抽样与分母。
summary 不把未完成的配对或阶段当作完整结果；运行中使用 status/tail。
两个 controller 配置 systemd Conflicts，避免全量与子集同时抢占同一组 CPU。
不要在旧全量批次的 checkout 上升级代码来恢复：其冻结配置与失败证据需保留。

## 从干净 checkout 建立相同子集

先 source `/srv/macroatlas/env.sh`，进入独立 checkout 的 ATLAS，再执行：

```bash
python scripts/phase4/correctness_gate.py
python scripts/phase4/prepare.py --output generated/server-official --b 2
python scripts/phase4/campaign.py plan \
  --official generated/server-official \
  --phases e3-original e4-matched e5-auto --paper-fraction 0.25 \
  --output /srv/macroatlas/experiments/phase4-quarter \
  --controller-unit macroatlas-phase4-quarter \
  --workers 5 --memory-mb 16384 --repeats 3 --timeout 180 --seed 20260922
python scripts/phase4/campaign.py install-service /srv/macroatlas/experiments/phase4-quarter
```

服务安装后还需部署专用 wrapper 及与旧 controller 的 Conflicts 配置。
建立计划与安装服务均不会自动启动实验。
