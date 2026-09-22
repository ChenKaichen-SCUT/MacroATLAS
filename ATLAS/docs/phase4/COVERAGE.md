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
| peterson | 30 | 0 | 0 |
| voting_machine | 10 | 0 | 0 |
| robot | 20 | 0 | 0 |
| weakening | 78 | 0 | 0 |
| 总计 | 1109 | 0（0%） | 521（46.98%） |

原样：1,011 个候选字母表含 U，98 个未知 raw constraint。U-free 变体：580 个 raw constraint 未识别，8 个输入 loop 为空而不满足宏 lasso 约定。U-free 支持任务的原始总节点界限范围 B=2–264；不可统一假定 B≤15。

在原论文 623 个任务内，U-free 支持 485 个（77.85%）；约束 case studies 原样仍未进入宏路径。Phase 4 不为改善 coverage 悄悄放松约束或扩展识别器。AUTO 原样结果预计全部为 original fallback，必须报告这一事实。

机器数据：[official coverage](preflight/official-coverage.csv)、[matched coverage](preflight/matched-coverage.csv)、[supported list](preflight/matched-supported_tasks.txt)、[paper provenance](preflight/paper-provenance.json)。正式服务器应重新运行 prepare，记录新环境与列表 hash。
