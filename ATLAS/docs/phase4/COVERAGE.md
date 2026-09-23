# 官方 artifact 覆盖审计

只运行 parser/analyzer，没有用求解结果挑选输入。b=2；数据来自 frozen benchmark，checksum 已与 Zenodo 对照。

目录共有 1,247 个 `.trace`：1,109 个 ATLAS 格式，138 个 LTLSketcher 等其他工具格式。另有脚本和模型等文件，artifact 一致性检查总计 1,252 个 benchmark 文件。不能把扩展名相同当作同一种输入。

原论文 notebook 使用的 5 个 ATLAS 结果表通过路径反向匹配得到 623 个原论文任务：485 unconstrained、30 Peterson、10 voting、20 repair、78 weakening。这是自动发现结果，不在 runner 中硬编码任务数量。

| ATLAS family | 原样数量 | 原样 Macro 支持 | U-free 共同变体支持 |
| --- | ---: | ---: | ---: |
| 5to10Traces | 190 | 0 | 190 |
| baseTest | 42 | 0 | 42 |
| disjunctedExistence | 29 | 0 | 29 |
| equal | 42 | 0 | 42 |
| increasingNumVariables | 56 | 0 | 56 |
| moreDetailedTest | 126 | 0 | 126 |
| ltlsketch（ATLAS 格式扩展） | 486 | 0 | 36 |
| peterson | 30 | 0 | 30 |
| voting_machine | 10 | 0 | 10 |
| robot | 20 | 20 | 20 |
| weakening | 78 | 78 | 78 |
| 总计 | 1109 | 98（8.84%） | 659（59.42%） |

原样：1,011 个任务的候选字母表含 U；Robot 20 与 Weakening 78 本来就是 U-free，因此 AUTO 在这 98 个任务使用 Macro，其余回退。U-free 变体完整识别论文四个 constrained family 的固定模板；其余 450 个未知 raw constraint 继续 fail closed。有限 trace 按原 ATLAS 的末状态 stutter 语义处理。U-free 支持任务的原始总节点界限可超过 264，Robot 的 depth 输入会展开成 B=2050；求解器使用渐进 cost scope，不一次展开完整 B。

在原论文 623 个任务内，U-free matched 支持全部 623 个：485 个 unconstrained 与 138 个 constrained。原样 AUTO 支持 Robot/Weakening 98 个（15.73%），其余 525 个回退。约束识别按完整 canonical block 精确匹配，未知或残余 Alloy 文本仍拒绝；没有把任意 raw Alloy 当作已支持。AUTO 与 matched 仍须分开报告。

机器数据：[official coverage](preflight/official-coverage.csv)、[matched coverage](preflight/matched-coverage.csv)、[supported list](preflight/matched-supported_tasks.txt)、[paper provenance](preflight/paper-provenance.json)。正式服务器应重新运行 prepare，记录新环境与列表 hash。
