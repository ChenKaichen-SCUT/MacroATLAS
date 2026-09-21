# MacroATLAS

MacroATLAS 在 [ATLAS](https://github.com/cmu-soda/ATLAS) v1.0.2 基础上实现
保留语法约束状态的 unary semantic quotient 基础模块。

当前第一阶段包含：

- `UnaryNormalizer`：对 `!, X, F, G` 的 unary word 计算规范语义类型。
- `ConstraintAutomata`：propositional、NNF、CNF、DNF、required proposition 及惰性乘积自动机。
- `FiberTable`：按 `(qIn, semanticType, nonEmpty, qOut)` 分组，通过 BFS 选择最短、字典序最小代表。

实现保持原 ATLAS 求解器行为，当前未接入 MacroDAG 或 MaxSAT 主求解流程。
Java 8 和 Java 21 上的 40 个测试均已通过，包含穷举正确性检查和原 CLI 示例回归。

## 仓库内容

| 路径 | 内容 |
| --- | --- |
| [`ATLAS/`](ATLAS/) | 完整 ATLAS 源码、原始数据和依赖，以及 MacroATLAS 第一阶段改进 |
| [`ATLAS/UPSTREAM.md`](ATLAS/UPSTREAM.md) | 上游来源、版本及本仓库的收录方式 |
| [`MacroATLAS_Prototype_Phase1_Implementation_Guide.md`](MacroATLAS_Prototype_Phase1_Implementation_Guide.md) | 第一阶段实现规格 |
| [`ATLAS/docs/phase1/IMPLEMENTATION_REPORT.md`](ATLAS/docs/phase1/IMPLEMENTATION_REPORT.md) | 文件职责、API、设计说明和复现命令 |
| [`ATLAS/docs/phase1/validation/TEST_RESULTS.md`](ATLAS/docs/phase1/validation/TEST_RESULTS.md) | 全部测试与 baseline regression 结果 |
| [`Constrained LTL Specification Learning from Examples.pdf`](Constrained%20LTL%20Specification%20Learning%20from%20Examples.pdf) | ATLAS 对应论文 |
| [`The Complexity of Learning LTL, CTL and ATL.pdf`](The%20Complexity%20of%20Learning%20LTL%2C%20CTL%20and%20ATL.pdf) | 相关理论参考论文 |

构建输出和本地缓存不纳入版本控制；原有 `ATLAS/lib` 依赖包含在仓库中。

## 构建与测试

安装 JDK 8 或更高版本及 Maven，然后执行：

```bash
git clone https://github.com/ChenKaichen-SCUT/MacroATLAS.git
cd MacroATLAS/ATLAS
mvn -B clean verify
```

CLI 使用方式参见原始 [ATLAS README](ATLAS/README.md) 和
[第一阶段实现报告](ATLAS/docs/phase1/IMPLEMENTATION_REPORT.md)。

## 后续开发与提交

`ATLAS/` 是本仓库直接跟踪的普通源码目录，不是 Git submodule。
克隆本仓库即可取得其全部内容，无需额外初始化子模块。

在 MacroATLAS 根目录统一管理所有后续改动：

```bash
git status
git add .
git commit -m "Describe the change"
git push origin main
```

本仓库的 `origin` 为 `ChenKaichen-SCUT/MacroATLAS`。
上游 ATLAS 的来源与原始说明保留在仓库内。
