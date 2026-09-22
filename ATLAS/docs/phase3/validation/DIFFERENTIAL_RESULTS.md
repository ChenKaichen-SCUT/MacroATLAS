# Phase 3 差分验证

2026-09-22 UTC；对应代码 `450bb2576e13576e81729a6e38a4adb4541bbf23`。Java 8/21 执行相同固定种子测试；计数是正确性覆盖，不是性能结果。

## 独立 reference

`TinyReferenceEnumerator` 仅在 test 源码内。它逐个构造拓扑编号的所有 ordered DAG，允许共享和同父 LEFT/RIGHT 相同，过滤不可达节点；并枚举 protected identity 到符合标签节点的所有单射。没有调用 macro decomposition、FiberTable、normalizer 或 symbolic encoding。

每个有根 DAG 都有根编号最后的拓扑编号，因此不是只枚举树。reference 用 Phase 2 的 test-only `UFreeLassoOracle` 分类，用自动机检查 compositional acceptance，用具体 DAG 的 parent/children 关系检查 identity，再独立比较目标 tuple。

## 普通任务

- Seed `20260922`；243 个任务，84 SAT、159 UNSAT，0 mismatch。
- 200 个交叉变化任务：AP 1–2、B 1–4、b 0–2；NOT/X/F/G、AND/OR/IMPLIES、五类 automata、模板、乘积；包含正负矛盾。
- 3 个 B=5、b=0/1/2 边界任务。
- 40 个混合 unary alphabet 任务：同一任务允许 `! X F G`，组合 Imply、NNF/RequiredProp/product；每个任务两个正样本与两个负样本。
- Lasso 长度 1–4，prefix/loop 分割随机且 loop 非空。
- 每例比较 SAT/UNSAT、最小展开大小、预测分类和完整接受状态。生产 verifier 同时验证模型/展开 size、anchor q-state、每条 edge 的全位置语义、skeleton/fiber 重提取。

机器记录：[phase3-tiny-results.txt](phase3-tiny-results.txt)。

## Repair

- Seed `920226`；50 个任务，30 SAT、20 UNSAT，0 mismatch。
- B 3–5、b=1、protected AND/F/literal；变化 old-edge 集、样本、直接 child/reachability、NoDAGReuse 与 LEFT!=RIGHT。
- 包含无法保留的旧边、零可保留边、重复端口指向同一旧 pair。
- 比较严格 tuple `(最大 kept distinct pairs, 最小 expanded size)`，不以公式字符串相同作为正确性条件。
- 零可保留边测试曾发现 bundled `maxsome` 的常量简化问题，当前用硬基数界限搜索解决；详见 [ENCODING](../ENCODING.md)。

机器记录：[phase3-repair-results.txt](phase3-repair-results.txt)。

## 全位置 semantic equality

B=5 的无约束、全 unary catalog 有 44 个 fibers。枚举单命题长度 1–4 的全部 98 个 lassos，含所有 loop 起点和值序列；每个 fiber 的 SemanticType vector 与代表词的独立语法求值完全相等，共 4,312 次完整 Boolean vector 比较。

机器记录：[phase3-semantics-results.txt](phase3-semantics-results.txt)。原 Phase 2 的 94,176 次穷举 root-vector 比较和 seed=20260921 的 1,200 个随机案例继续通过。

## 显式边界回归

另有针对最优大小 s 的 B=s-1/s/s+1、确实需要两个 binary nodes 的 b=0/1/2、共享 unary anchor、protected slot 顺序反转、protected 数超过 B、直接边冲突、NoDAGReuse 冲突的测试。

同父两条空 port 指向同一 target 的 distinct parent 数是 1；同 target 的两条非空 fiber 在展开后有不同私有 heads 和两个真实 parents。损坏 size 和 fiber assignment 必须被 verifier 拒绝；在 AUTO dispatcher 中注入损坏 fiber 后，original 调用次数仍为 0。
