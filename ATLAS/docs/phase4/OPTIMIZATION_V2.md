# MacroATLAS 求解优化与修复

旧的 1/4 pilot 发现三类问题：Macro 在共同解出的任务上偏慢；B≥10 大量超时，B=134/264 还会 parser stack overflow 或 translation capacity error；论文 138 个 constrained case 没有进入 matched 比较。旧结果只用于定位问题，修复后不得继续作为正式性能结果。

## 正确性修复

- 完整 canonical block 识别 Peterson 30、Voting 10、Robot repair 20、Weakening 78 个任务。未知 Alloy 仍 fail closed。
- 缺失命题值按 false 解释；有限 trace 的最后状态自环，与 Original ATLAS 一致。
- Robot 的 named atoms 在 soft repair 中可不出现在最终公式；只有实际保留的 identity 进入解码和验证。
- repair 严格按 `(最大 kept, 最小 expanded size)` 优化。先逐步扩大 cost scope 寻找 kept 的理论上界；不能因为小 scope 容不下最优修复就提前删除旧边。
- ATLAS-B 能从 Robot 的复合 fact 中只移除 soft objective，保留同一 fact 内的硬约束；未使用 named atoms 不再被错误强制为根可达。

## 搜索域缩减

1. Alloy 大 union 改为平衡树，消除深递归 parser overflow。
2. valuation 从一个三元关系改为每条 trace 的二元字段，B=264 的代表任务不再触发 universe capacity error。
3. fiber 按 `(qIn,qOut,empty/nonempty,所有样本上的完整布尔函数)` 做精确商；同类只留最短、字典序最小代表。
4. 约束树自动机做可达代数的接受等价最小化。Weakening 从 35 个状态降到 15，scope 8 的 fibers 从 390 降到 109。
5. cost scope 从 8 开始渐进扩大，只编码当前尺寸可能使用的 fibers 和 Units。Robot 的 B=2050 不再生成 2050 个 Unit。
6. 匿名 anchors 固定为 active prefix 和拓扑编号；有 protected identities 时只重命名匿名部分。Robot 代表任务的求解时间由 24 秒进一步降到约 2.4 秒。
7. 等价的 ultimately-periodic traces 规范化后只编码一次；最终 verifier 仍逐条检查所有原始样本。`equal/0012` 从 1000 条降到 597 个不同无限词、位置数从 5000 降到 2740。

所有缩减都保持候选公式、约束接受性和两个优化目标。独立 verifier 使用展开后的具体语法、原 automaton 和原始 traces，不依赖 Alloy valuation 得出最终正确性结论。

## 定向开发诊断

以下是同一工作区、OpenWBOWeighted、单次本地运行的开发诊断，不是正式实验或统计结论。时间为 solverSec；`>90` 表示该开发运行超时。

| 任务 | 修复前 Macro | 修复后 Macro | 修复后 ATLAS-B |
| --- | ---: | ---: | ---: |
| Robot RA `final21` | >90 s | 2.40 s | 16.45 s |
| Weakening antecedent `10_10_10` | >90 s | 4.65 s | 0.78 s |
| Peterson `base/liveness1` | 39.9 s | 2.14 s | 59.3 s（较早单次） |
| Voting `voting3` | 13.2 s | 1.52 s | 4.58 s（较早单次） |
| Equal `0012`（1000 traces） | 48.3 s | 14.64 s | 未在本轮重测 |

这组结果说明已消除已知的结构性瓶颈，同时也显示 Macro 并非每类任务都更快；例如 Weakening 的 concrete baseline 仍明显更快。正式结论必须在新 commit 上按统一 180 秒、同机、同任务、一次运行协议重跑完整 quarter/full campaign。
