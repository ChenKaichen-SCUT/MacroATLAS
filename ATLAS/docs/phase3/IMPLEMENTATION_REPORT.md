# Phase 3 实现报告

日期：2026-09-22 UTC。

`PHASE2_BASE_COMMIT=92551ef83c7d083635eaa51d0a2666e12d986969`。
Phase 3 代码提交：`450bb2576e13576e81729a6e38a4adb4541bbf23`。验证记录与 README 在后续文档提交中收录，文档提交不改代码。

## 完成内容

Phase 3 已使 MacroDAG 进入真实搜索：直接选择 anchors、ports、constraint states 和 fibers；使用原 AlloyMax 后端求精确有界最优解；再经 Phase 2 展开得到可验证的 FormulaDag。默认原 ATLAS CLI 保持原路径。

支持 U-free 公式、已有五类 compositional automata 与乘积、两类 fixed template、NoDAGReuse、LeftNotEqualRight、named direct child/reachability/root，以及 protected old-edge repair。具体 raw Alloy 白名单与不支持边界见 [SUPPORTED_FRAGMENT](SUPPORTED_FRAGMENT.md)。编码及 repair 正确性说明见 [ENCODING](ENCODING.md)。

## 文件职责

新增生产文件均位于 `src/main/kotlin/cmu/s3d/ltl/macro/`：

| 文件 | 职责 |
| --- | --- |
| `constraint/FixedTemplateAutomaton.kt` | `G(Prop)`、response template 与 root operator automata |
| `search/MacroConstraintPlan.kt` | 不含 raw text 的可信编译计划、identity constraints、objectives、模式和结构化原因 |
| `search/RecognizedConstraintAnalyzer.kt` | 对 TaskParser raw constraints 做完整 canonical block 识别，未知部分 fail closed |
| `search/MacroCompilationContext.kt` | 可达状态饱和、deterministic catalog、lasso successor/future/succPow |
| `search/MacroAlloyModelBuilder.kt` | skeleton、状态一致性、SemanticType 真值、identity、精确 size 编码 |
| `search/MacroAssignmentDecoder.kt` | Alloy 字段值到 MacroDag，保留 protected identities |
| `search/FinalSolutionVerifier.kt` | Phase 2 round trip、完整 q-state、B/b、identity、目标与逐位置独立语法求值 |
| `search/MacroLearner.kt` | 原后端调用、repair 有界优化、结果 metadata/debug artifacts |
| `search/MacroTaskDispatcher.kt` | OFF/AUTO/FORCE 分支，禁止异常和 UNSAT 触发 fallback |

唯一修改的既有生产文件为 `app/CLI.kt`，增加 opt-in 参数与分支、对子进程传递参数、宏模式失败时非零退出。Phase 1/2、原 LTLLearner/TaskParser 和 pom/依赖均未修改。

新增测试位于 `src/test/kotlin/cmu/s3d/ltl/macro/search/`：`MacroSearchTest`、`MacroDomainsTest`、`MacroDifferentialTest`、`MacroCliTest`、test-only `TinyReferenceEnumerator`。五个真实 parser fixture 位于 `src/test/resources/macro/`。规格文件收录在仓库根目录。

## API 与保证

```kotlin
val analysis = RecognizedConstraintAnalyzer.analyze(task, binaryBudget = 1)
// Supported.plan 可传入泛型 helper 创建 MacroLearner；Unsupported 含稳定 reason enum。

val plan = MacroConstraintPlan(
    automaton = ProductConstraintAutomaton(listOf(NnfAutomaton())),
    propositions = listOf("x0"), nodeBudget = 5, binaryBudget = 1
)
val result = MacroLearner(plan, task.positiveExamples, task.negativeExamples).solve()
// result.dag 非空时已通过 verifier；空表示 B,b 内 UNSAT。
```

Registry 从 literal states 出发饱和允许操作符，重用同一个 product owner。catalog 在整个 solve/repair 多次调用间缓存。模型只见编号；输出保留完整状态与 identity。

`K=min(B,p+3b+2)`；virtual root 不计节点。acyclicity 使用严格传递闭包而非 slot-index 拓扑序；所有 active anchors 必须可达。大小为 active anchors 加全部 active port 的代表长度。模型中的 B 个 Unit 用于分配与计数，不携带语法或真值。

Lasso 编码按 SemanticType 直接计算每个位置；representative 仅决定长度和最终重建。Verifier 用具体节点语法的独立不动点 evaluator 检查所有 anchor/edge position，并用 Phase 2 verifier 再提取 skeleton/fiber。

最优性仅针对计划指定的 B、b、字母表、有限约束及 identity 语义。repair 优先级严格为最大 kept pair 数，再最小展开大小。默认原 ATLAS 的优化目标和迭代 scope 策略没有被改为宏目标。

## 运行方式

在 `ATLAS/` 目录中：

```bash
mvn -B clean verify
mvn -B dependency:build-classpath -Dmdep.outputFile=target/runtime-classpath.txt -DincludeScope=runtime

java -Djava.library.path=./lib \
  -cp "target/classes:lib/AlloyMax-1.0.3.jar:$(cat target/runtime-classpath.txt)" \
  cmu.s3d.ltl.app.CLIKt \
  -f src/test/resources/macro/repair.trace \
  --macro force --macro-max-binary 1 --macro-max-nodes 4 \
  --macro-debug target/repair-debug -T 60
```

AlloyMax 是 system-scope bundled JAR，需要显式加到 runtime classpath。可加 `-s OpenWBOWeighted` 使用原生 OpenWBO。`ATLAS/lib/open-wbo` 保持 executable Git mode 100755。

宏模式输出原九列 CSV，并额外输出 JSON metadata；父进程沿用原 stderr/stdout 合并方式，因此需要纯 CSV 的消费者可使用默认模式或从 debug `analysis.json` 读取元数据。`--traces` 批量模式为不同相对路径创建独立 debug 子目录。建议每次验收使用新的 debug 目录；开始时 verification 状态置为 IN_PROGRESS，成功后置 PASSED，UNSAT 明确为 NOT_APPLICABLE_UNSAT。

## 验收与必要调整

见 [测试结果](validation/TEST_RESULTS.md)、[差分结果](validation/DIFFERENTIAL_RESULTS.md)、[CLI smoke](validation/SMOKE_RESULTS.md)。包含 Java 8/21 全量测试、243 个普通任务、50 个 repair 任务、独立逐位置语义比较、原 CLI 修改前后对照。原有 72 项测试全部保留。

相对指引的必要实现选择：

1. 用独立 `ConstraintStateRegistry`，未修改 Phase 1 的接口。
2. 使用 Alloy transitive closure 编码 DAG 无环，不把 slot 索引当作 rank。
3. size 通过互斥 Unit 分配编码，不增加原始 unary syntax 搜索节点。
4. repair 使用基数界限二分、多次同后端精确 size 优化，以处理 bundled `maxsome none` 的已发现边界问题。
5. 严格 raw grammar 仅识别可证明全部 protected nodes 可达的 repair；允许删除旧节点的原 robot 模板继续安全回退。
6. 未增加 optional invariant weakening 或通用 FO 自动机。未知约束、候选 U、未支持目标仍拒绝/回退。

后续可扩展更多经过证明的 canonical templates、允许旧节点删除的独立 repair 语义，以及经过正确性验证的 catalog/model 优化。本阶段未运行全量论文 benchmark，未声称速度提升。
