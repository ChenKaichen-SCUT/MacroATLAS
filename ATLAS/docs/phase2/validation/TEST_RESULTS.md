# Phase 2 验证记录

日期：2026-09-21（UTC）。Phase 1 起点 `920836e2b2b4d61820be6d39da5b731c757e3b23`；本记录对应的 Phase 2 代码提交 `0a654f36f49a5ccf89a7bf099f8e8e486265ed52`。验证报告与 README 更新作为随后的文档提交，不改变该代码。

## 构建及原有回归

| 环境 / 命令 | 结果 | 证据 |
| --- | --- | --- |
| 改动前 OpenJDK 21.0.12，`mvn -B -Dstyle.color=never clean verify` | 原有 40 项全通过；JAR 生成成功 | [baseline](baseline-test-summary.txt) |
| 改动后 Temurin 1.8.0_462，`mvn -B -Dstyle.color=never clean verify` | 72 项通过，0 失败/错误/跳过；JAR 生成成功 | [Java 8](java8-test-summary.txt) |
| 改动后 OpenJDK 21.0.12，`mvn -B -Dstyle.color=never clean verify dependency:build-classpath -Dmdep.outputFile=target/runtime-classpath.txt -DincludeScope=runtime` | 72 项通过，0 失败/错误/跳过；JAR 生成成功 | [Java 21](java21-test-summary.txt) |

Maven 3.6.3、Kotlin 1.7.0、JVM target 1.8、AlloyMax 1.0.3 均沿用原版本。最终 49 个 Phase 2 class 文件的 major version 全部为 52。原 solver/parser/Phase 1/pom 共 25 个文件已与起点逐字节比较，无变化；OpenWBO 内容不变，仅 Git executable mode 修正为 100755。

## 各类正确性覆盖

| 类别 | 实际验证范围 | 结果 |
| --- | --- | --- |
| FormulaDag | literal、unary、binary、共享、LEFT==RIGHT、缺根/child、cycle、unreachable、重复 NodeId、空命题、Map key 不匹配、集合不可变、Map 顺序无关、12,001 节点深链和环 | PASS |
| 真实 adapter | example0000 的 renderer/root/child IDs/round trip；自定义真实 Alloy 解的共享 unary；example0007 的 U 可提取但拒绝 macro；每 atom 只读取一次；数字 label/identity 分离和非法 arity | PASS |
| Constraint bridge | 5 个基础 automata、包含全部五个分量的 product、共享 child 单次转移、完整 root state、accepting/nonaccepting 情况 | PASS |
| Eligibility | U、禁止的 unary、错 protected ID、未处理的 Alloy text、不完备 automaton；即使全部 protected 也不猜测 raw text；Unsupported 不进入 extractor | PASS |
| Anchors/ports | 虚拟根 unary chain、binary 两侧链、empty edge、共享 literal、同父双端口/不同父共享 unary、protected interior/root、唯一内部覆盖、source+kind 身份、稳定顺序 | PASS |
| Fiber bridge | FF/GG 缩短、!G/F! NNF fiber 不同、empty/!! 区分、完整 product owner/state、所有原 port/root qOut 交叉核对 | PASS |
| Expansion/verifier | 原图精确恢复、canonical 严格结构、anchor/protected ID+label、共享 target、root state/acceptance、节点数不增长、7→5 示例、skeleton+fiber 再提取稳定、ID 碰撞处理 | PASS |
| Verifier 负向测试 | 损坏 word、缺少 port、改变 anchor label、错误 protected set/count/root state、非最短 representative 均返回结构化 violations | PASS |
| Port budget | 每个 round trip 检查端口数=1+2b+u，且≤p+3b+2；每个 non-anchor unary ID 恰出现一次 | PASS |
| 原 40 项 | 原 12 个 ATLAS 测试及 Phase 1 的 28 个测试在两种 JDK 下均保留并通过 | PASS |

## 独立无限 lasso 语义

测试 oracle 不调用 normalizer、FiberTable 或 macro 代码，只按原 FormulaDag 的节点类型和 LassoTrace 的 successor 关系求值。F/G 遍历完整可达循环；逐位置计算 !/X/AND/OR/IMPLIES；比较的是 root 的全部位置，不仅位置 0。

- 穷举 60 个 DAG：两命题上所有语法 size≤3 的 U-free 树公式，加 6 个共享 unary 子树的 DAG。
- 穷举每个 DAG 的全部 protected subsets，以及 NNF/CNF/DNF/Propositional/RequiredProp 和三分量 product，共 2,616 次 round trip。
- lasso 长度 1–2、所有 loop starts、两命题全部 valuation，共 36 个 lassos，完成 94,176 次 root Boolean vector 比较，全部相同。
- 随机 seed=20260921，共 1,200 个合法 DAG/lasso/profile/protected-set 组合。生成池至 26 个节点，lasso 长度至 12；每例再反转 Map 插入顺序重复重建，canonical DAG 完全一致。
- 随机案例中 643 个含 sharing、817 个有 protected nodes、76 个严格减少节点；全部通过 root state、identity、kernel bound 和真值检查。失败会记录 seed、iteration 和完整必要 fixture。
- 真实 example0000 的全部 5 个 positive 与 5 个 negative lasso，原/新公式的根向量相同，位置 0 分类与样本标签一致。

上述计数用于正确性覆盖，未运行论文 benchmark，也未做速度提升推断。

## 原 CLI 前后对照

同一目录、相同 classpath、同一 `src/test/resources/samples2ltl/example0000.trace`、`OpenWBOWeighted` 和 `-T 60`，执行原 `cmu.s3d.ltl.app.CLIKt`。两次进程都返回 0。

| 运行 | 公式 | solvingTime 秒 | stdout |
| --- | --- | --- | --- |
| 修改前 | `!(F(x0))` | 0.383 | [baseline-cli.csv](baseline-cli.csv) |
| 修改后 | `!(F(x0))` | 0.376 | [after-cli.csv](after-cli.csv) |

表头及全部 8 个非时间字段经程序化比较完全相同；耗时只记录，不作为 benchmark。

## 全部测试明细

共 72 项，其中新增 32 项；时间来自两个环境的 Surefire XML。每项均 PASS。

| 测试类 | 方法 | 所属 | Java 8 秒 | Java 21 秒 |
| --- | --- | --- | --- | --- |
| `SimpleLTLLearnerTests` | `testSimpleG` | 原有 | 0.056 | 0.068 |
| `SimpleLTLLearnerTests` | `testSimpleUntil` | 原有 | 0.666 | 0.623 |
| `ConstraintAutomataTests` | `automataAgreeWithIndependentStructuralPredicatesOnGeneratedFormulas` | 原有 | 0.061 | 0.055 |
| `ConstraintAutomataTests` | `cnfAcceptsExactlyTheRequiredExamples` | 原有 | 0 | 0 |
| `ConstraintAutomataTests` | `dnfAcceptsExactlyTheRequiredExamples` | 原有 | 0 | 0.001 |
| `ConstraintAutomataTests` | `emptyAndNestedProductsHaveWellDefinedBehavior` | 原有 | 0.002 | 0.001 |
| `ConstraintAutomataTests` | `invalidStatesAreAbsorbingAndNnfRetainsAtlasBinarySyntax` | 原有 | 0.001 | 0 |
| `ConstraintAutomataTests` | `nnfAcceptsExactlyTheRequiredExamples` | 原有 | 0 | 0 |
| `ConstraintAutomataTests` | `productAppliesTransitionsComponentWiseAndRequiresAllComponentsToAccept` | 原有 | 0 | 0.001 |
| `ConstraintAutomataTests` | `productStatesAreLazyInternedImmutableAndOwned` | 原有 | 0.001 | 0.001 |
| `ConstraintAutomataTests` | `propositionalOnlyRejectsAllTemporalOperatorsIncludingUntil` | 原有 | 0 | 0 |
| `ConstraintAutomataTests` | `requiredPropositionUsesExactAtlasNamesAndPropagatesEveryOperator` | 原有 | 0.001 | 0 |
| `FiberTableTests` | `boundsEmptyDomainsAndMissingLookupsAreExplicit` | 原有 | 0.015 | 0.013 |
| `FiberTableTests` | `everyAllowedAlphabetSubsetMatchesBruteForce` | 原有 | 0.009 | 0.007 |
| `FiberTableTests` | `fiberBfsMatchesBruteForceForAnAutomatonWithRecoverableRejection` | 原有 | 0.065 | 0.034 |
| `FiberTableTests` | `fiberBfsMatchesBruteForceUpToLength7ForAllReachableProductStates` | 原有 | 0.702 | 0.536 |
| `FiberTableTests` | `fiberBfsMatchesBruteForceUpToLength7ForEveryBaseAutomatonState` | 原有 | 0.099 | 0.081 |
| `FiberTableTests` | `fiberReplayUsesTheActualNestingDirection` | 原有 | 0.001 | 0 |
| `FiberTableTests` | `fibersAndTableViewsAreImmutableValueKeys` | 原有 | 0 | 0 |
| `FiberTableTests` | `lexicalTiesAreResolvedAfterEachWholeLayerAndIgnoreAlphabetInputOrder` | 原有 | 0.001 | 0.001 |
| `FiberTableTests` | `nnfDistinguishesEquivalentSyntaxAndKeepsBothFibers` | 原有 | 0 | 0.001 |
| `FiberTableTests` | `nonemptyIdentityAndInputStatesRemainDistinct` | 原有 | 0 | 0.001 |
| `UnaryNormalizerTests` | `atlasOperatorAdaptersRespectArityAndRejectUntilInUnaryWords` | 原有 | 0 | 0 |
| `UnaryNormalizerTests` | `canonicalWordReplaysEveryTypeAndUsesOuterToInnerOrder` | 原有 | 0 | 0 |
| `UnaryNormalizerTests` | `knownIdentitiesAndDualityArePreserved` | 原有 | 0 | 0 |
| `UnaryNormalizerTests` | `normalizationIsIdempotentAndCanonicalLengthNeverIncreasesThroughLength8` | 原有 | 0.066 | 0.07 |
| `UnaryNormalizerTests` | `normalizationPreservesTruthOnExhaustiveSmallLassos` | 原有 | 0.057 | 0.048 |
| `UnaryNormalizerTests` | `normalizationPreservesTruthOnSeededRandomLassosAndLongWords` | 原有 | 0.009 | 0.009 |
| `UnaryNormalizerTests` | `prefixMatchesEveryFrozenTransition` | 原有 | 0 | 0 |
| `UnaryNormalizerTests` | `wordsAreImmutableValueKeysAndOrderIsExplicit` | 原有 | 0.001 | 0.001 |
| `DagAnalysisTests` | `allFiveBaseAutomataAndProductsEvaluateTheFullGraph` | Phase 2 | 0.039 | 0.041 |
| `DagAnalysisTests` | `eligibilityReturnsAllStructuralProfileReasonsAndDoesNotConfuseLabelsWithIds` | Phase 2 | 0.122 | 0.12 |
| `DagAnalysisTests` | `literalAndValidAndInvalidUnaryRootsKeepTheirFullStates` | Phase 2 | 0.001 | 0.002 |
| `DagAnalysisTests` | `nonTotalAutomataAreUnsupportedAndEligibilitySnapshotsAreImmutable` | Phase 2 | 0.004 | 0.005 |
| `DagAnalysisTests` | `sharedSubtreesAreEvaluatedOnceEvenWhenReferencedBySeveralParentsAndPorts` | Phase 2 | 0.013 | 0.013 |
| `DagAnalysisTests` | `unknownRawAlloyIsRejectedEvenWhenEveryNodeIsProtected` | Phase 2 | 0.011 | 0.01 |
| `AlloySolutionDagExtractorTests` | `actualAlloySharingIsRetainedAndRawConstraintsAreNotSilentlyClaimed` | Phase 2 | 0.212 | 0.251 |
| `AlloySolutionDagExtractorTests` | `adapterReadsEachFullAtomOnceAndSeparatesNumberedLabelsFromIdentity` | Phase 2 | 0.013 | 0.015 |
| `AlloySolutionDagExtractorTests` | `malformedAdapterArityAndCyclesFailExplicitly` | Phase 2 | 0.013 | 0.01 |
| `AlloySolutionDagExtractorTests` | `realSampleExtractsRendersAndCompletesTheMacroRoundTrip` | Phase 2 | 0.308 | 0.283 |
| `AlloySolutionDagExtractorTests` | `untilRemainsRepresentableFromARealSolutionButIsIneligible` | Phase 2 | 0.031 | 0.047 |
| `FormulaDagTests` | `deepDagsAndDeepCyclesUseIterativeValidation` | Phase 2 | 0.04 | 0.04 |
| `FormulaDagTests` | `graphOrderAndEqualityAreIndependentOfMapInsertionOrder` | Phase 2 | 0.001 | 0.001 |
| `FormulaDagTests` | `literalUnaryBinaryAndSharedChildrenHaveCorrectStructure` | Phase 2 | 0 | 0 |
| `FormulaDagTests` | `missingRootChildCycleUnreachableDuplicatesAndBlankPropositionsAreRejected` | Phase 2 | 0.036 | 0.03 |
| `FormulaDagTests` | `snapshotsCannotBeMutatedThroughSourceCollectionsOrViews` | Phase 2 | 0 | 0 |
| `MacroKernelTests` | `decompositionAndFreshIdsAreDeterministicAcrossMapOrdersAndAvoidCollisions` | Phase 2 | 0.005 | 0.005 |
| `MacroKernelTests` | `differentParentsPreserveTheSameSharedUnaryIdentity` | Phase 2 | 0.001 | 0.001 |
| `MacroKernelTests` | `directEdgesAndRepeatedLiteralTargetsRemainSharedAndEmpty` | Phase 2 | 0 | 0 |
| `MacroKernelTests` | `emptyAndNonemptyIdentityContextsNeverMerge` | Phase 2 | 0.001 | 0.001 |
| `MacroKernelTests` | `nnfEquivalentContextsRetainDifferentFibersAndNonacceptingState` | Phase 2 | 0.002 | 0.001 |
| `MacroKernelTests` | `portsUseSourceIdentityAndSnapshotsAreImmutable` | Phase 2 | 0.001 | 0 |
| `MacroKernelTests` | `productOwnerAndAllPortStateCrossChecksStayConsistent` | Phase 2 | 0.001 | 0.002 |
| `MacroKernelTests` | `protectedInteriorAndProtectedRootCutPathsAtTheirExactIdentities` | Phase 2 | 0 | 0.001 |
| `MacroKernelTests` | `sameParentTwoPortsMakeTheirSharedUnaryChildAnAnchor` | Phase 2 | 0.001 | 0.002 |
| `MacroKernelTests` | `twoBranchExampleShrinksFromSevenNodesToFive` | Phase 2 | 0.001 | 0.001 |
| `MacroKernelTests` | `unprotectedRootChainIsAbsorbedByTheVirtualRootPort` | Phase 2 | 0.001 | 0 |
| `MacroKernelTests` | `verifierReturnsStructuredViolationsForBrokenWordsSkeletonIdentityAndCounts` | Phase 2 | 0.007 | 0.007 |
| `MacroSemanticsTests` | `exhaustiveSmallDagProtectedSubsetProfileAndLassoCombinationsPreserveEveryRootPosition` | Phase 2 | 0.48 | 0.216 |
| `MacroSemanticsTests` | `extractedSampleRetainsPositiveAndNegativeTraceClassification` | Phase 2 | 0.136 | 0.124 |
| `MacroSemanticsTests` | `oracleHandlesInfiniteLoopsAllOperatorsAndEveryPositionIndependently` | Phase 2 | 0 | 0.001 |
| `MacroSemanticsTests` | `seededRandomDagSharingProtectedSubsetsAndAllProfilesPreserveSemantics` | Phase 2 | 0.334 | 0.32 |
| `TaskParserTests` | `testBase0007` | 原有 | 7.679 | 8.911 |
| `TaskParserTests` | `testExample0000` | 原有 | 0.09 | 0.098 |
| `TaskParserTests` | `testExample0001` | 原有 | 0.088 | 0.134 |
| `TaskParserTests` | `testExample0002` | 原有 | 0.027 | 0.034 |
| `TaskParserTests` | `testExample0003` | 原有 | 0.028 | 0.033 |
| `TaskParserTests` | `testExample0004` | 原有 | 0.028 | 0.033 |
| `TaskParserTests` | `testExample0005` | 原有 | 0.089 | 0.095 |
| `TaskParserTests` | `testExample0006` | 原有 | 0.079 | 0.092 |
| `TaskParserTests` | `testExample0007` | 原有 | 0.021 | 0.024 |
| `TaskParserTests` | `testf_01_nw_010_type_0` | 原有 | 0.08 | 0.071 |

## 交付边界

没有修改 AlloyMax/MaxSAT 模型，没有新增 --macro CLI，没有对 U 做 normalization，没有解析或宣称支持任意 Alloy text。当前模块用于既有 ATLAS 解的可验证后处理。Phase 2 无剩余实现 TODO；搜索编码和 recognized constraint compiler 属于 Phase 3。
