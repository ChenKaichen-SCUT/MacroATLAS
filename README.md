# MacroATLAS

MacroATLAS 在 [ATLAS](https://github.com/cmu-soda/ATLAS) v1.0.2 基础上实现
保留语法约束状态的 unary semantic quotient 基础模块。

第一阶段包含：

- `UnaryNormalizer`：对 `!, X, F, G` 的 unary word 计算规范语义类型。
- `ConstraintAutomata`：propositional、NNF、CNF、DNF、required proposition 及惰性乘积自动机。
- `FiberTable`：按 `(qIn, semanticType, nonEmpty, qOut)` 分组，通过 BFS 选择最短、字典序最小代表。

第二阶段在真实 ATLAS 已求得的公式 DAG 上实现后处理闭环：

- 从 `LTLLearningSolution` 提取保留完整 atom identity 和 sharing 的不可变 `FormulaDag`。
- 执行约束求值、eligibility 检查及 anchor/port/unary path 分解。
- 生成带完整 fiber 的 `MacroDag`，支持原始身份重建和最短代表重建。
- 用生产侧 round-trip verifier 和独立 lasso 语义测试验证压缩正确性。

第三阶段增加可选的直接 MacroDAG 搜索：有限约束状态域与 fiber catalog、
anchor/port 搜索编码、精确 lasso 语义、展开大小最小化、protected identity 和 repair 优化。
复用原 AlloyMax 后端，并通过 Phase 2 重建及独立语义检查验证输出。
默认 CLI 保持原 ATLAS 行为；`--macro auto/force` 显式启用新路径。
支持范围与复现说明见 [Phase 3 实现报告](ATLAS/docs/phase3/IMPLEMENTATION_REPORT.md)。

第四阶段增加 Original ATLAS 复现实验入口、同域 ATLAS-B baseline、覆盖清单生成、
隔离并行运行器、正确性门禁、合成数据与结果图表脚本。当前 v4 MacroATLAS
包含小公式最优界与 constrained 搜索约束优化；原论文 Original 路径继续保留。
实验协议见 [Phase 4 实验协议](ATLAS/docs/phase4/EXPERIMENT_PROTOCOL.md)，
换服务器开展全量实验所需的代码、数据与任务划分见
[全量实验交接说明](ATLAS/docs/phase4/FULL_RUN_HANDOFF.md)。
已完成的 RQ1 tiny exhaustive 与全量 E4 matched 单次运行，其原始数据、
可复算汇总和结论见 [2026-09-23 实验结果](ATLAS/experiment_artifacts/2026-09-23/README.zh-CN.md)。
RQ4 synthetic scalability 的逐运行数据与适用范围见
[2026-09-24 RQ4 结果](ATLAS/docs/phase4/RQ4_RESULTS_2026-09-24.md)。
RQ2 E4 matched 编码规模的逐案例数据与分析见
[2026-09-24 RQ2 结果](ATLAS/docs/phase4/RQ2_RESULTS_2026-09-24.md)。

## 仓库内容

| 路径 | 内容 |
| --- | --- |
| [`ATLAS/`](ATLAS/) | 完整 ATLAS 源码、原始数据和依赖，以及 MacroATLAS Phase 1–4 代码 |
| [`ATLAS/UPSTREAM.md`](ATLAS/UPSTREAM.md) | 上游来源、版本及本仓库的收录方式 |
| [`MacroATLAS_Prototype_Phase1_Implementation_Guide.md`](MacroATLAS_Prototype_Phase1_Implementation_Guide.md) | 第一阶段实现规格 |
| [`ATLAS/docs/phase1/IMPLEMENTATION_REPORT.md`](ATLAS/docs/phase1/IMPLEMENTATION_REPORT.md) | 文件职责、API、设计说明和复现命令 |
| [`ATLAS/docs/phase1/validation/TEST_RESULTS.md`](ATLAS/docs/phase1/validation/TEST_RESULTS.md) | 全部测试与 baseline regression 结果 |
| [`MacroATLAS_Prototype_Phase2_Implementation_Guide.md`](MacroATLAS_Prototype_Phase2_Implementation_Guide.md) | 第二阶段实现规格 |
| [`ATLAS/docs/phase2/IMPLEMENTATION_REPORT.md`](ATLAS/docs/phase2/IMPLEMENTATION_REPORT.md) | DAG 适配、压缩重建 API、约束边界与实现说明 |
| [`ATLAS/docs/phase2/validation/TEST_RESULTS.md`](ATLAS/docs/phase2/validation/TEST_RESULTS.md) | 第二阶段完整验证结果 |
| [`MacroATLAS_Prototype_Phase3_Implementation_Guide.md`](MacroATLAS_Prototype_Phase3_Implementation_Guide.md) | 第三阶段实现规格 |
| [`ATLAS/docs/phase3/IMPLEMENTATION_REPORT.md`](ATLAS/docs/phase3/IMPLEMENTATION_REPORT.md) | 宏搜索实现、边界和运行方式 |
| [`ATLAS/docs/phase3/validation/TEST_RESULTS.md`](ATLAS/docs/phase3/validation/TEST_RESULTS.md) | 第三阶段 Java 8/21、差分与 CLI 验证 |
| [`MacroATLAS_Phase4_Experiment_Guide.md`](MacroATLAS_Phase4_Experiment_Guide.md) | 第四阶段实验规格 |
| [`ATLAS/scripts/phase4/`](ATLAS/scripts/phase4/) | 数据准备、运行、验证和分析脚本 |
| [`ATLAS/docs/phase4/COVERAGE.md`](ATLAS/docs/phase4/COVERAGE.md) | 原始 artifact 与 U-free 变体的真实支持范围 |
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
[Phase 3 支持范围](ATLAS/docs/phase3/SUPPORTED_FRAGMENT.md)。

启用宏搜索时必须显式指定二元节点预算，例如 `--macro force --macro-max-binary 1`；
仅对 U-free 且可完整识别的约束提供有界精确最优保证。

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
