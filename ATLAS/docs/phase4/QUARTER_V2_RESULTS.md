# Phase 4 1/4 实验：Original、v1 与 v2

统计截止 2026-09-23。v1 结果来自服务器 `/srv/macroatlas/experiments/phase4-quarter-once`，提交 `e3654b4`；v2 来自 `/srv/macroatlas/experiments/phase4-quarter-v2-changed-once`，提交 `d8a56ed`。两批均已完整结束。两批使用相同的 156 个分层抽样论文任务、同一台 `ecs-564a`、Java 8u462、OpenWBOWeighted、180 秒限时、5 个绑定 CPU 的 worker、每 worker 16 GiB 内存与 4 GiB JVM 堆，每个任务/算法运行一次。v1/v2 共同的 121 个 matched 输入以及 Original 与 v2 AUTO 的 156 个原样输入，文件 SHA-256 均相同。

`solved` 指 SAT 或 UNSAT；AUTO 的 `FALLBACK` 在原算法求得 SAT/UNSAT 时也计入。PAR-2 将未解任务按 360 秒计。以下值来自经 `validate_results.py` 校验的 `merged/raw.csv`，未把不同行为域的耗时直接相除。

## 同域 matched 比较

| 任务集合 | 版本/算法 | solved | TIMEOUT | ERROR | PAR-2 (秒) |
| --- | --- | ---: | ---: | ---: | ---: |
| v1/v2 共同的 121 题 | v1 ATLAS-B | 52/121 | 62 | 7 | 214.53 |
| v1/v2 共同的 121 题 | v1 MacroATLAS | 39/121 | 73 | 9 | 250.80 |
| v1/v2 共同的 121 题 | v2 ATLAS-B | 55/121 | 62 | 4 | 206.70 |
| v1/v2 共同的 121 题 | v2 MacroATLAS | 60/121 | 61 | 0 | 197.34 |
| v2 全部 156 题 | v2 ATLAS-B | 81/156 | 71 | 4 | 188.27 |
| v2 全部 156 题 | v2 MacroATLAS | 95/156 | 61 | 0 | 160.64 |

在相同的 121 题上，v2 MacroATLAS 比 v1 多解 21 题，旧版解出的 39 题新版均能解出；这 39 题上的 v1/v2 耗时比中位数为 1.55、几何均值为 1.70。新旧 SAT 解共有 39 题，其最优目标值没有变化。v1 中 MacroATLAS/ATLAS-B 共同解出的 39 题，ATLAS-B/MacroATLAS 耗时比中位数 0.56；v2 在共同的 121 题中双方都解出的 51 题，该比值中位数 0.86、几何均值 0.91。v2 已提升覆盖和整体 PAR-2，但在普通无约束题的共同解出部分仍没有稳定的中位速度优势。

v2 新增的 35 个 constrained 题如下。该部分 MacroATLAS 解出 35/35，ATLAS-B 解出 26/35；双方共同解出的 26 题，ATLAS-B/MacroATLAS 耗时比中位数 4.41。但 Weakening consequent 的 9 个 `UNSAT` 有下述结构性限制，不能把它们当作有意义的原任务求解成功。

| constrained 类别 | 抽样数 | v2 ATLAS-B solved | v2 MacroATLAS solved | 共同解出耗时比中位数 |
| --- | ---: | ---: | ---: | ---: |
| Peterson | 8 | 8 | 8 | 5.53 |
| Robot repair | 5 | 4 | 5 | 11.25 |
| Voting | 2 | 2 | 2 | 2.81 |
| Weakening antecedent | 11 | 8 | 11 | 0.48 |
| Weakening consequent | 9 | 4 | 9 | 0.62；结构性 UNSAT，见下文 |

v2 完整 156 题中，双方都解出 77 题，MacroATLAS 独自解出 18 题，ATLAS-B 独自解出 4 题，双方都未解出 57 题。共同解出部分的耗时比中位数 0.92、几何均值 1.21；这两个指标方向不同，不能概括为“每类任务都加速”。

## Original 与 AUTO 原样输入

| 模式 | SAT（含成功回退） | UNSAT | TIMEOUT | ERROR | PAR-2 (秒) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original，旧批次 E3 | 102 | 0 | 50 | 4 | 147.55 |
| v1 AUTO | 102 | 0 | 50 | 4 | 148.11 |
| v2 AUTO | 102（86 回退 + 16 Macro） | 9 | 41 | 4 | 129.39 |

v2 AUTO 在 156 题中仅 25 题实际使用 Macro，其他 131 题回退 Original；86 个成功回退任务的 Original/AUTO 耗时比中位数约为 1.005。9 个新的 `UNSAT` 中，5 题原 Original 超时，**4 题原 Original 已返回 SAT**；同时有 4 题从 Original 超时变为 AUTO SAT。因此 `solved` 虽由 102 增至 111，SAT 总数仍是 102。`AUTO` 的 111 不能直接解释为对原任务多解了 9 题。

这 4 个 SAT→UNSAT 均为 Weakening consequent。Original 的具体解为 `G(->(x0,|(&(x1,x2),x1)))`，有 `->`、`|`、`&` 三个二元节点；v2 matched/AUTO 的 `b=2` 将其排除。Weakening consequent 模板本身至少需要这三个二元节点，所以抽中的 9 个 consequent 题在当前 matched 域下必然 UNSAT。ATLAS-B 和 MacroATLAS 对其中 4 题都求得 UNSAT，ATLAS-B 在另 5 题超时；MacroATLAS 在 9 题都求得 UNSAT。这里没有观察到两个 matched 求解器结果冲突，但 AUTO 不能被称为原始无二元节点上限任务的同域替代。应在原样 AUTO 路径中对缩域后 UNSAT 回退 Original，或将其明确标为 bounded-domain 答案；Weakening consequent 的正式对比需至少以 `b=3` 重新运行双方，并记录新协议与结果，不能改写本次数据。

## 剩余问题与证据边界

- v2 MacroATLAS 的 61 个超时均出现在 121 个无约束 matched 题中；`B≤5` 只有 1/41 超时，`B≥20` 为 21/29 超时。瓶颈主要是求解阶段，不是 analyzer/fiber 构建。v2 Macro 没有 ERROR，原 v1 的 9 个 ERROR 已消失，但大节点界限仍未普遍可解。
- v2 Weakening 的 20 题虽然全部 SAT/UNSAT，双方共同解出的 12 题中 ATLAS-B/MacroATLAS 耗时比中位数只有 0.53；特别是 consequent 的 UNSAT 证明会把 Macro 的 scope 扩至 18。该类任务需优先优化空域预检查和约束求解。
- ATLAS-B 仍有 4 个 `baseTest` 任务触发 Alloy 三元 valuation 的 `Translation capacity exceeded`；Original 在同四个原样任务上也报此错。v2 Macro 在 matched 域中没有这种 ERROR。
- v2 的 312 个 matched run 和 156 个 AUTO run 均通过完整性校验；没有 `VERIFICATION_FAILED` 或已解 matched 对的目标值冲突。25 个原样 AUTO Macro 任务与其 matched Macro 任务输入 SHA 相同、SAT/UNSAT 状态相同，SAT 目标值也相同。UNSAT 没有独立的最终解验证证书；matched 一致性与 tiny reference gate 不能替代所有规模的完备性证明。
- 这是按固定 seed 抽取的 1/4 探索批次，每个任务只有一次测量，5 个 worker 仍会共享缓存和内存带宽。Original 原样任务允许 `U` 且二元运算符数量无上限，matched 任务排除 `U` 且 `b=2`；两类结果只比较覆盖、状态和部署行为，不给出 Original/Macro 直接速度比。

原始记录：旧批次的 `e3-original/merged/raw.csv` SHA-256 为 `a07c9c8dbdd1be6c19330d7f07e38e79c6136672c17b9ad46231080fa810357c`，旧 `e4-matched/merged/raw.csv` 为 `19e035c9ab4a56411c761b14e3d0f1e4cba0163aeb4dbd12f0f9cfbc17981b86`；新批次的 `e4-matched/merged/raw.csv` 为 `3b6df9f812aa5a414182991f14f0ea95f9831b05f9dccb8905182770eefd982b`，`e5-auto/merged/raw.csv` 为 `938d0219917eafcc55e3c837cf5b6ff2a6d414948899f68e432460b7a5b92c49`。两批的 `plan.json`、完整任务产物和处理后 CSV 均保留在各自目录。
