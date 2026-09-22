# 已知边界与失败分析计划

正式失败分析尚待完整运行，不能根据少量 pilot 选择性汇报成功案例。

已确认的结构性限制：

1. 原样官方 Macro coverage 为 0；AUTO 全回退。
2. U-free 变体仍有 580 个未知约束、8 个空 loop 输入；本阶段不改 capability。
3. 原任务 B 可达 264；kernel 小不保证 catalog/model/MaxSAT 总开销小。
4. Original ATLAS 单位置 trace 的空 next 表达式及不同长度 trace 的 X successor 边界行为保留在 Original 复现路径；ATLAS-B 的适配独立记录。Original 若返回语义不合格 witness，会停止并保存证据，不当作已解任务。
5. 原有 Java/AlloyMax 依赖的构建警告保留。RSS guard、JVM OOM 与时间超时分开统计。

`analyze.py` 自动列出 Macro >2x slower、仅 baseline solved、仅 Macro solved。进一步结合 B/K、catalog size、repair 与 trace 规模分析；不得只删除 timeout 后平均时间。

开发期间 ATLAS-B repair witness 验证失败及目标表达式问题已修复并加入双后端回归；见 [CORRECTNESS.md](CORRECTNESS.md)。此前 matched pilot 不用于任何性能汇总，最终预检重新运行。
