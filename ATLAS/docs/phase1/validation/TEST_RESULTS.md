# 第一阶段验证记录

验证日期：2026-09-21（UTC）。基线：ATLAS v1.0.2 / `f5134d2a3b08e762bf16ebfbd4988a94daa35f88`。

## 构建与兼容性

| 环境/命令 | 测试 | 结果 | 日志 |
| --- | --- | --- | --- |
| 修改前，OpenJDK 21.0.12，`mvn test` | 原有 12 项 | 12 通过，0 失败/错误/跳过 | [baseline](baseline-test-summary.txt) |
| 修改后，Temurin 1.8.0_462，`mvn -B -Dstyle.color=never clean verify` | 40 项 | 40 通过，0 失败/错误/跳过；JAR 生成成功 | [Java 8](java8-test-summary.txt) |
| 修改后，OpenJDK 21.0.12，`mvn -B -Dstyle.color=never clean verify dependency:build-classpath -Dmdep.outputFile=target/runtime-classpath.txt -DincludeScope=runtime` | 40 项 | 40 通过，0 失败/错误/跳过；JAR 生成成功 | [Java 21](java21-test-summary.txt) |

已检查最终产物中全部 31 个 macro class 文件，major version 均为 52（Java 8）。Maven 为 3.6.3，Kotlin/AlloyMax 版本沿用原 pom。

Java 8 校验环境位于 `/tmp/macroatlas-jdk8/jdk8u462-b08`；通过该次进程的 JAVA_HOME/PATH 使用，未更改系统默认 Java。下载使用 Temurin 官方 release：`OpenJDK8U-jdk_x64_linux_hotspot_8u462b08.tar.gz`；已与 release 的 `.sha256.txt` 核对，SHA-256 为 `5d64ae542b59a962b3caadadd346f4b1c3010879a28bb02d928326993de16e79`。

## README 示例回归

示例为 `src/test/resources/samples2ltl/example0000.trace`，内容对应 README 的 task 示例。修改前后均从同一个工作目录使用相同 `CLIKt` 命令、classpath、`OpenWBOWeighted` 和 60 秒 timeout，进程返回 0；未修改求解器、样本或参数。

| 运行 | 学到的公式 | solvingTime（秒） | stdout |
| --- | --- | --- | --- |
| 修改前 | `!(F(x0))` | 0.374 | [baseline-cli.csv](baseline-cli.csv) |
| 修改后 | `!(F(x0))` | 0.39 | [after-cli.csv](after-cli.csv) |

程序化比较 CSV 表头及全部 8 个非时间字段：完全一致。时间只记录，不作为性能实验或回归门槛。报告中使用 runtime classpath 的可复制命令也已实际执行成功。

## 全部测试结果

下面时间来自 Maven Surefire XML。每行在两个 Java 环境中均通过；共 12 个原有测试、28 个新增测试。

| 测试类 | 测试方法 | Java 8 秒 | Java 21 秒 | 结果 |
| --- | --- | --- | --- | --- |
| `SimpleLTLLearnerTests` | `testSimpleG` | 0.056 | 0.064 | PASS |
| `SimpleLTLLearnerTests` | `testSimpleUntil` | 0.688 | 0.653 | PASS |
| `ConstraintAutomataTests` | `automataAgreeWithIndependentStructuralPredicatesOnGeneratedFormulas` | 0.06 | 0.051 | PASS |
| `ConstraintAutomataTests` | `cnfAcceptsExactlyTheRequiredExamples` | 0.011 | 0.01 | PASS |
| `ConstraintAutomataTests` | `dnfAcceptsExactlyTheRequiredExamples` | 0.013 | 0.008 | PASS |
| `ConstraintAutomataTests` | `emptyAndNestedProductsHaveWellDefinedBehavior` | 0.07 | 0.071 | PASS |
| `ConstraintAutomataTests` | `invalidStatesAreAbsorbingAndNnfRetainsAtlasBinarySyntax` | 0.001 | 0 | PASS |
| `ConstraintAutomataTests` | `nnfAcceptsExactlyTheRequiredExamples` | 0 | 0 | PASS |
| `ConstraintAutomataTests` | `productAppliesTransitionsComponentWiseAndRequiresAllComponentsToAccept` | 0.001 | 0.001 | PASS |
| `ConstraintAutomataTests` | `productStatesAreLazyInternedImmutableAndOwned` | 0.035 | 0.026 | PASS |
| `ConstraintAutomataTests` | `propositionalOnlyRejectsAllTemporalOperatorsIncludingUntil` | 0 | 0 | PASS |
| `ConstraintAutomataTests` | `requiredPropositionUsesExactAtlasNamesAndPropagatesEveryOperator` | 0 | 0.001 | PASS |
| `FiberTableTests` | `boundsEmptyDomainsAndMissingLookupsAreExplicit` | 0.013 | 0.015 | PASS |
| `FiberTableTests` | `everyAllowedAlphabetSubsetMatchesBruteForce` | 0.007 | 0.009 | PASS |
| `FiberTableTests` | `fiberBfsMatchesBruteForceForAnAutomatonWithRecoverableRejection` | 0.043 | 0.053 | PASS |
| `FiberTableTests` | `fiberBfsMatchesBruteForceUpToLength7ForAllReachableProductStates` | 0.561 | 0.683 | PASS |
| `FiberTableTests` | `fiberBfsMatchesBruteForceUpToLength7ForEveryBaseAutomatonState` | 0.089 | 0.099 | PASS |
| `FiberTableTests` | `fiberReplayUsesTheActualNestingDirection` | 0 | 0.001 | PASS |
| `FiberTableTests` | `fibersAndTableViewsAreImmutableValueKeys` | 0 | 0.001 | PASS |
| `FiberTableTests` | `lexicalTiesAreResolvedAfterEachWholeLayerAndIgnoreAlphabetInputOrder` | 0.001 | 0.001 | PASS |
| `FiberTableTests` | `nnfDistinguishesEquivalentSyntaxAndKeepsBothFibers` | 0 | 0 | PASS |
| `FiberTableTests` | `nonemptyIdentityAndInputStatesRemainDistinct` | 0 | 0.001 | PASS |
| `UnaryNormalizerTests` | `atlasOperatorAdaptersRespectArityAndRejectUntilInUnaryWords` | 0 | 0 | PASS |
| `UnaryNormalizerTests` | `canonicalWordReplaysEveryTypeAndUsesOuterToInnerOrder` | 0 | 0 | PASS |
| `UnaryNormalizerTests` | `knownIdentitiesAndDualityArePreserved` | 0 | 0 | PASS |
| `UnaryNormalizerTests` | `normalizationIsIdempotentAndCanonicalLengthNeverIncreasesThroughLength8` | 0.156 | 0.087 | PASS |
| `UnaryNormalizerTests` | `normalizationPreservesTruthOnExhaustiveSmallLassos` | 0.072 | 0.081 | PASS |
| `UnaryNormalizerTests` | `normalizationPreservesTruthOnSeededRandomLassosAndLongWords` | 0.018 | 0.014 | PASS |
| `UnaryNormalizerTests` | `prefixMatchesEveryFrozenTransition` | 0 | 0 | PASS |
| `UnaryNormalizerTests` | `wordsAreImmutableValueKeysAndOrderIsExplicit` | 0 | 0.001 | PASS |
| `TaskParserTests` | `testBase0007` | 8.522 | 8.774 | PASS |
| `TaskParserTests` | `testExample0000` | 0.107 | 0.131 | PASS |
| `TaskParserTests` | `testExample0001` | 0.103 | 0.109 | PASS |
| `TaskParserTests` | `testExample0002` | 0.036 | 0.041 | PASS |
| `TaskParserTests` | `testExample0003` | 0.034 | 0.04 | PASS |
| `TaskParserTests` | `testExample0004` | 0.032 | 0.034 | PASS |
| `TaskParserTests` | `testExample0005` | 0.098 | 0.127 | PASS |
| `TaskParserTests` | `testExample0006` | 0.081 | 0.101 | PASS |
| `TaskParserTests` | `testExample0007` | 0.02 | 0.025 | PASS |
| `TaskParserTests` | `testf_01_nw_010_type_0` | 0.098 | 0.099 | PASS |

## 指南完成条件

| 条件 | 验证结果 |
| --- | --- |
| 原 ATLAS build | Java 8 和 21 clean verify 成功 |
| baseline regression | 同一 README 示例前后成功，非时间输出完全一致 |
| unary fixed identities / transition table | 全部通过 |
| unary 长度 ≤8 | 全部 87,381 个 word 的 invariant 通过 |
| 五种基础 automata / product | 全部示例及独立结构谓词测试通过 |
| generated fibers replay | 全部生成条目通过 |
| B=0…7 minimality | 与独立 brute-force 完整 map 完全相同 |
| NNF 语义相同、语法不同回归 | `!G` 与 `F!` 同语义但保持不同 fiber |
| Java 8 compatibility | 实际 JDK 8 clean build/test + major version 52 检查通过 |
| 不修改原 solver | 与 HEAD 逐字节对比原生产文件和 pom；`git diff HEAD` 为空，全部变更为新增文件 |

没有进行论文 benchmark、solver 重写或 MacroDAG/MaxSAT 集成。
