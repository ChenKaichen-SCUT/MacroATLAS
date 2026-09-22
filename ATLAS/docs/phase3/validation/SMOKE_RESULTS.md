# Phase 3 CLI smoke

2026-09-22 UTC；对应代码 `450bb2576e13576e81729a6e38a4adb4541bbf23`。以下均经真实 `TaskParser -> CLI -> MacroLearner -> decoder -> verifier`，非手工拼装最终公式。

## 新增的 U-free fixture

通用命令（工作目录 ATLAS，classpath 见实现报告）：

```bash
java -Djava.library.path=./lib -cp "$ATLAS_RUNTIME_CP" cmu.s3d.ltl.app.CLIKt \
  -f src/test/resources/macro/repair.trace \
  --macro force --macro-max-binary 1 --macro-debug target/repair-debug
```

| Fixture | 结果 | B/b/p/K | Q / fibers | 展开大小 | 验证 |
| --- | --- | --- | --- | --- | --- |
| literal.trace | `x0` | 3/1/0/3 | 1 / 24 | 1 | PASSED |
| eventually.trace | `F(x0)` | 3/1/0/3 | 1 / 2 | 2 | PASSED |
| next.trace | `X(x0)` | 3/1/0/3 | 1 / 4 | 2 | PASSED |
| nnf.trace | `!(x0)` | 3/1/0/3 | 3 / 87 | 2 | PASSED |
| repair.trace | `F(x0)`，kept=1 | 4/1/2/4 | 1 / 34 | 2 | PASSED |

五例在 Java 8/21 下均返回 0，默认 SAT4JMax；另对 repair 用 OpenWBOWeighted 实测，同样得到 kept=1、size=2 并通过验证。记录见 [smoke metadata](smoke-metadata.json)、[fixture summary](phase3-smoke-results.txt)、[OpenWBO macro output](openwbo-macro-smoke.txt)。

原测试资源的全部 samples2ltl fixtures 都允许 U，因此没有将它们静默改为 U-free。新增三例无约束、一例 recognized NNF、一例 repair，原 fixtures 保留用于默认路径和 U 回退检查。

## 原默认 CLI 前后对照

对未修改的 `src/test/resources/samples2ltl/example0000.trace`，使用 `-s OpenWBOWeighted -T 60`，修改前后均为 9 列 CSV、公式 `!(F(x0))`、退出码 0。程序逐字段比较表头和全部非 solvingTime 字段，完全一致。

证据：[baseline-cli.csv](baseline-cli.csv)、[after-cli.csv](after-cli.csv)。`MacroCliTest` 另检查默认与显式 `--macro off` 输出相同，且不出现 macro metadata。时间只记录，不比较性能。

## 模式与失败路径

- 原 example0000 + AUTO：`solverMode=ORIGINAL`，reason 为候选字母表包含 U。
- 相同输入 + FORCE：结构化 Unsupported，父进程亦非零退出。
- 合法但不在白名单中的 `fact { some DAGNode }` + AUTO：UNKNOWN_CUSTOM_ALLOY_CONSTRAINT，原后端继续求解。
- next fixture + AUTO、B=1/b=0：`solverMode=MACRO`、UNSAT，未进入 original。
- 注入 decoder/verifier invariant failure：AUTO 抛错，无 fallback。

未知约束的 fallback fixture 使用至少两个位置：原 ATLAS 在全部轨迹仅一个位置时会生成空的 `next =` Alloy 表达式；本阶段未修改该原有行为。新增宏路径的一位置 lasso 正常通过。
