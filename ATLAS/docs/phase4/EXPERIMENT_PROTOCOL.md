# Phase 4 实现与实验协议

本阶段交付实验代码、覆盖审计与资源预检。正式同机 baseline、完整 matched/AUTO、3 次重复及论文图表的性能结论，等待用户提供服务器后执行；本目录不把预检当作完整 Phase 4 实验完成。

## 冻结与来源

- `macroatlas-phase3-frozen` 指向 `03d2ed26d3060277b505eedf24bf9edf76fc1600`。
- 冻结前重新通过原 89 项测试、243 普通任务、50 repair 任务及默认 CLI 回归。
- 初次正式 pilot 暴露 correctness/coverage 和 scalability 问题后已停止旧实验；修复版本扩展了论文四个 constrained family 的精确 analyzer，并要求使用新 commit 重跑，旧性能数据不混用。
- 新增 `experiment/` 是实验入口与 matched baseline，原 CLI、LTLLearner、TaskParser 均不修改。
- [Zenodo artifact](https://zenodo.org/records/14578202) 的 1,252 个 benchmark 文件与本地逐字节一致；下载 checksum 见 [artifact-provenance.json](artifact-provenance.json)。不把历史 CSV 的时间作为当前 baseline。

## 三种问题必须分开

1. **论文 artifact 复现**：Original ATLAS 原样输入、原求解及原目标。`paper_tasks.txt` 从原论文 notebook 使用的五个历史 CSV 自动反向定位输入，当前 623 个任务。记录原 `solvingTime` 和另测端到端耗时；记录 expected string 是否匹配，但等价公式不按字符串自动认错。
2. **Matched 主实验**：ATLAS-B 与 MacroATLAS-B 在相同 U-free `.trace`、B、b、约束、目标下比较。当前自动支持 659 个（含论文 485 个 unconstrained、138 个 constrained，以及 artifact 扩展 ltlsketch 的 36 个）；双方共同使用同一支持列表。
3. **AUTO deployment**：Original 与 AUTO 对原样工作负载。当前原样支持 Robot/Weakening 98 个，其余 1,011 个 ATLAS-format 任务回退；必须分别报告 macro-used 与 fallback。

## ATLAS-B 的必要变化

仅添加 `#BinaryNodes<=b` 不足以同域：原 ATLAS 最小化 `l+r`，逐步增大整体 atom scope；Macro 最小化根可达的实际节点数。实验类 `MatchedAtlasLearner` 复用原 `generateAlloyModel` 的具体语法 DAG、trace semantics 和已识别的 raw 硬约束，但：

- `#childrenAndSelfOf[root]<=B`，根可达 binary 数 <=b；所有非 literal 节点必须可达。
- 用一个受硬约束等于 `childrenAndSelfOf[root]` 的独立 relation `ExperimentCost.used`，再 `minsome ExperimentCost.used`，代替原边集合目标。bundled AlloyMax 对直接闭包表达式的 soft 目标未正确优化；明确 relation 经 SAT4JMax/OpenWBOWeighted 对照验证。
- 原 ATLAS 给每个 AP 分配固定 literal；未使用 AP 不计根公式大小，因此总 atom scope 为 `B+#AP`，根可达节点仍受 B 限制。metadata 同时记录两个数，不能将原子总数伪称 B。
- repair 移除唯一受支持的 soft fact，用与 Macro 相同的精确 kept 基数搜索，再最小化节点数。硬 raw 约束保持。
- B 很大时双方从 cost scope 8 渐进扩大；第一次可行的最小尺寸解即为全局最小。repair 必须先按 scope 搜索理论最大 kept，不能在小 scope 过早接受较少旧边。
- 原 generator 的单位置 `next =` 空表达式仅在 ATLAS-B 适配成 `ordering/next = none->none`。Original 路径保留 artifact 行为。
- 原 generator 的 X successor 使用全局 ordering；当同任务 traces 长度不同时，较短 trace 可读到范围外的 valuation。ATLAS-B 将 successor 限定到当前 trace 的 `seqRange`，保证与 Macro 和独立具体 lasso 语义一致。Original 保留原样，若其结果验证失败则停止并报告。

新增 80 个参考任务比较 ATLAS-B/Macro/独立 DAG reference；另验证必须两个 binary nodes 的三命题合取。ATLAS-B 是显式改目标的公平比较基线，不冒充原论文未经修改的 Original ATLAS。

repair 的目标最优性与不同长度 trace 的 X 语义另在 SAT4JMax 和 OpenWBOWeighted 上回归。完整问题复现与修复记录见 [正确性说明](CORRECTNESS.md)。

## 运行协议

用户后续要求服务器并行执行。该部署使用 [并行协议](SERVER_DEPLOYMENT.md) 的 CPU/cgroup 隔离、
同题同 worker 和统一资源配额，并在 manifest 明示覆盖本节的串行默认设置。
已有单机 pilot 不与该服务器结果混合。

单任务一个 JVM，一次只跑一个 task，含原生 OpenWBO 子进程。`run.py` 采用仓库级文件锁防止两个控制器竞争；每个任务独立进程组，超时或 RSS guard 时杀死整个组。统一 OpenWBOWeighted，默认 180 秒，`-Xms512m -Xmx4g`；双方所有设置相同。

每次运行使用独立 `java.io.tmpdir`，子进程回收后删除 native solver 临时文件，避免超时任务填满系统 `/tmp`；`--keep-solver-temp` 可显式保留。模型、命令和结果日志始终保留。

`/usr/bin/time -v` 保存系统资源日志；另每 50ms 采样 JVM+native solver 进程组的 RSS 合计作为 peakRssKb。采样可能漏过更短峰值，共享页可能重复计算，不能声称精确 cgroup peak。`--memory-mb` 是相同的采样 RSS guard，不是内核硬配额；JVM heap limit 也不等于整任务内存。明确区分 TIMEOUT、JVM_OOM、RSS_LIMIT、进程错误和验证失败。

Formal 运行要求干净 Git commit 和匹配 commit/JVM/编译后应用/Alloy JAR/solver checksum 的 correctness certificate。`--pilot` 可在开发状态下跑，但 manifest 标记 pilot，所有图表与报告禁止作为正式性能证据。

每批保存环境、任务内容 hash、命令、随机排列、expected runs；每任务保存 stdout/stderr、metadata/analysis/timing/verification JSON、Alloy 模型与 resource.txt。已有输出目录拒绝覆盖。中断后保留 raw artifacts，使用新目录运行遗漏列表；不悄悄忽略缺失行。

## 复现命令

安装 JDK、Maven、Python 3.10+、GNU time；图表额外使用 matplotlib。Ubuntu 22.04 amd64 建议固定 Temurin 8u462（本地已验证）或统一同一个 Java 21 版本。

```bash
cd ATLAS
python3 -m pip install -r scripts/phase4/requirements.txt
python3 scripts/phase4/correctness_gate.py
python3 scripts/phase4/prepare.py --output generated/official --b 2

# E3：论文原样 Original；若要覆盖整个 artifact，改用 original_tasks.txt（1109 个）。
python3 scripts/phase4/run.py --suite original --root benchmark \
  --tasks generated/official/paper_tasks.txt --timeout 180 --repeats 1

# E4：支持列表自动生成，双方共同使用 U-free 变体。
python3 scripts/phase4/run.py --suite matched --root generated/official/matched_u_free \
  --tasks generated/official/matched/supported_tasks.txt --b 2 --timeout 180 --repeats 3

# E5：原样全工作负载；fallback 单独记录。
python3 scripts/phase4/run.py --suite auto --root benchmark \
  --tasks generated/official/original_tasks.txt --b 2 --timeout 180 --repeats 1

python3 scripts/phase4/validate_results.py results/COMMIT/MACHINE/BATCH
python3 scripts/phase4/analyze.py results/COMMIT/MACHINE/BATCH
```

可用 `--cpu 0-3` 给两个方法相同 affinity；必须先确认物理核心映射，避免把超线程 sibling 当作独立物理核。保持串行，固定 governor/后台负载，保存配置。额外三次重复应在正式运行前固定任务集与 seed；若仅重跑 common-solved，须与全量 solved/PAR-2 表分开报告。

## 指标与检查

7 类状态 SAT/UNSAT/TIMEOUT/UNSUPPORTED/FALLBACK/ERROR/VERIFICATION_FAILED。Fallback 附 outcome，算 deployment 的结果，永远不算 macro-used。宏与 matched SAT 必须 PASSED；UNSAT 标注 NOT_APPLICABLE_UNSAT，不虚构 SAT verifier 证书。Original 额外做包含 U 的具体 lasso 求值，标 TRACE_PASSED，raw 约束仍由原后端保证。

PAR-2 在每次原始 run 上计算：solved 为实际 wall time，其余罚 2T；不删除 timeout。重复任务的 runtime 用 median，common-solved 要求所有计划重复均 solved。报告 median/geomean/IQR speedup、四种 solved 配对、peak RSS、错误和 fallback 数。

Alloy reporter 暴露 primary/total Boolean vars 与 total clauses。保存每轮最大值与 translation count；没有可靠 hard/soft split，不编造。modelBytes 是完整模型 UTF-8 字节的单轮最大值。时间分为 analysis/registry/fiber/encoding/backend parse+translate+solve/decode/verify；JVM、IO 和非测量段属于 end-to-end residual，不将不完整 component sum 当作 total。

任何 verifier failure 或 matched SAT/UNSAT/objective tuple mismatch，runner 立即停止；validator 再检查重复/缺失/commit/域/状态/验证标记。正式实验若出现 correctness bug，修复并全回归、新 tag、旧性能结果作废重跑。

## Selective reruns

Campaign plans record an explicit ordered algorithm list for each phase. When
the frozen Original artifact has not changed, omit `e3-original` and use
`--auto-variants auto` to reuse its prior result instead of timing it again.
Run both `--matched-variants atlas-b macro` whenever either matched encoding
changed so their comparison uses the same code revision and environment.
