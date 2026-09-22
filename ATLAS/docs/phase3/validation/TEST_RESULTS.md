# Phase 3 验证记录

日期 2026-09-22 UTC。Phase 2 起点 `92551ef83c7d083635eaa51d0a2666e12d986969`；Phase 3 代码 `450bb2576e13576e81729a6e38a4adb4541bbf23`。

| 环境 | 命令 | 结果 |
| --- | --- | --- |
| 修改前 OpenJDK 21.0.12 | `mvn -B -Dstyle.color=never clean verify` | 72 tests，0 failures/errors/skipped |
| Temurin 1.8.0_462 | `mvn -B -Dstyle.color=never clean verify` | 89 tests，0 failures/errors/skipped，JAR 生成成功 |
| OpenJDK 21.0.12 | `mvn -B -Dstyle.color=never clean verify dependency:build-classpath -Dmdep.outputFile=target/runtime-classpath.txt -DincludeScope=runtime` | 89 tests，0 failures/errors/skipped，JAR 生成成功 |

构建摘要：[baseline](baseline-test-summary.txt)、[Java 8](java8-test-summary.txt)、[Java 21](java21-test-summary.txt)。完整逐方法记录见 [test-cases.csv](test-cases.csv)。

原 72 项全部保留，新增 17 个 JUnit test methods；其中两个方法分别包含 243/50 个差分任务。没有用任务数量冒充 JUnit 方法数。

| 新测试类 | 方法数 | 主要覆盖 |
| --- | --- | --- |
| MacroDomainsTest | 4 | state saturation、product owner、catalog deterministic/replay、empty/nonempty、restricted alphabet、4,312 次 semantic vectors、fixed templates、严格 raw grammar |
| MacroSearchTest | 7 | literal/negation/SAT/UNSAT、B/b、共享 unary、response、protected order、identity、repeat port/pair、fresh heads、corrupt assignment |
| MacroDifferentialTest | 2 | 243 普通任务 + 50 repair 任务与独立 DAG reference 的最优值比较 |
| MacroCliTest | 4 | 默认与 OFF、AUTO/FORCE/U/unknown、宏 UNSAT、5 个真实 parser fixtures、debug、无内部错误 fallback |

Maven 3.6.3、Kotlin 1.7.0、JVM target 1.8、AlloyMax 1.0.3 沿用原配置。Phase 1/2、原 LTLLearner、TaskParser、pom 和 lib 内容均与基线一致；既有生产文件中仅 CLI 增加显式 opt-in 分支。

已逐字节核对 60 个既有源码、测试和依赖文件，除 CLI 外均未改变；新增 search 包的 65 个 class 文件均为 major version 52（Java 8）。

构建仍报告原有 Maven systemPath 和 compiler plugin version 警告；没有为本阶段升级依赖。默认 CLI 的表头、公式及所有非时间字段与修改前完全相同，见 [SMOKE_RESULTS](SMOKE_RESULTS.md)。

实际支持范围、raw whitelist 和未支持部分见 [SUPPORTED_FRAGMENT](../SUPPORTED_FRAGMENT.md)。不包含全量论文 benchmark，不作速度提升结论。
