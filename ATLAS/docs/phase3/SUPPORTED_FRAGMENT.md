# Phase 3 支持范围

Macro 模式在给定展开节点界限 B 和二元节点界限 b 内精确优化。B 不是 anchor 数；b 不是深度。结果不表示未限制 b 的全局最优。

## 入口与模式

- 默认或 `--macro off`：原 ATLAS 路径；不分析约束、不构建状态域或 fiber。
- `--macro auto --macro-max-binary b`：支持的任务使用宏搜索；只有结构化 Unsupported 才回退原 ATLAS。
- `--macro force --macro-max-binary b`：不支持即非零退出，原因写入诊断。
- `--macro-max-nodes B`：可选，默认 `Task.maxNumOfOP + Task.literals.size`，沿用输入任务的总节点界限映射。
- `--macro-debug DIR`：保存模型、状态域、fiber、解码 assignment、公式和验证结果。
- 原 `--solver/-s`、`--timeout/-T`、`--model/-m` 继续可用。宏模式仅接受已有 MaxSAT 后端；`--findAny` 和 `--expected` 的枚举目标不受支持。

宏 UNSAT 就是当前 B、b 下无解，不会回退。模型编译、求解、解码和验证异常均暴露为失败，不会伪装成 Unsupported。

## 公式与自动机

允许 literal、`! X F G & | ->`；候选字母表包含 `U` 时直接 Unsupported，即使最终公式可能不用 U。禁止静默删去 U。

支持 Phase 1 的 Propositional、NNF、CNF、DNF、RequiredProposition 和它们的乘积，以及新增的 `G(Prop)`、`G(Prop -> F(Prop))` 固定语法模板、根操作符约束。Prop 允许任意布尔联结，不包含时态操作。

公开 Kotlin API `MacroConstraintPlan` 接受有限且完全的自动机。调用者负责自动机确实有限；状态域按当前命题和允许操作符饱和，不为任意用户自动机证明终止性。

`.trace` 路径保留原 ATLAS 每个命题一个 literal identity 的语义。类型化 API 默认允许多个同标签 literal；可设置 `uniqueLiteralIdentities=true`。两条路径都允许多个同标签 unary/binary anchors，未用标签唯一性裁剪搜索。

## Raw Alloy 的严格识别

原 TaskParser 只保留 raw string。已检查 bundled AlloyMax 的 parser/AST：它能解析完整 Alloy，但原任务没有附带已解析且可证明等价的约束表示。这里使用完整 canonical block 的白名单，不尝试通用 Alloy 定理证明，也不将 raw text 注入宏模型。

忽略空白及 `//`、`--`、`/* */` 注释；仅接受完整、无剩余内容的声明和 `fact { BODY }`。多种约束可使用多个 fact 块合取。下列多行模板必须完整处于同一个 fact 中；任意改写、额外合取、任意 closure、量词或目标都不自动认作等价形式。

| Profile | BODY |
| --- | --- |
| Propositional | `all n: DAGNode \| n in (Literal + Neg + And + Or + Imply)` |
| NNF | `all n: Neg \| n.l in Literal` |
| Required proposition | `x0 in childrenAndSelfOf[root]`，命题必须属于本任务 |
| Root operator | `root in G`，也支持 Neg/X/F/And/Or/Imply |
| NoDAGReuse | `all n: DAGNode \| lone n.~(l+r)` |
| NoDAGReuse excluding literals | `all n: DAGNode - Literal \| lone n.~(l+r)` |
| LeftNotEqualRight | `no l & r` |

CNF：

```alloy
fact {
  all n: DAGNode | n in (Literal + Neg + And + Or)
  all n: Neg | n.l in Literal
  all n: Or | no childrenOf[n] & And
}
```

DNF 的最后一行替换为 `all n: And | no childrenOf[n] & Or`。

固定模板：

```alloy
fact {
  root in G
  all n: childrenAndSelfOf[root.l] | n in (Literal + Neg + And + Or + Imply)
}
```

```alloy
fact {
  root in G
  root.l in Imply
  root.l.r in F
  all n: childrenAndSelfOf[root.l.l] + childrenAndSelfOf[root.l.r.l] |
    n in (Literal + Neg + And + Or + Imply)
}
```

## Protected identities 与 repair

接受 `one sig F0 extends F {}` 形式，名字限定为 Neg/X/F/G/And/Or/Imply 加数字，标签必须是允许操作符。每个声明对应一个固定身份 slot。引用任务 literal（例如 x0）时使用其唯一命题身份。

以下每项各占一个 fact：

```alloy
fact { root = And0 }
fact { And0.l = F0 }
fact { And0.r = x0 }
fact { x0 in childrenOf[F0] }
fact { F0 in childrenAndSelfOf[root] }
fact { maxsome[2] subDAG[root] & (And0->F0 + F0->x0) }
```

所有 named identities 必须被硬约束证明从根可达：显式可达、root 等式，或从已证明可达的 named 节点出发的直接边/后代约束。仅 soft oldSpec 边不能证明可达。

因此，原 robot repair benchmark 中允许声明旧节点不出现在根子图的写法会回退；本阶段没有擅自把“允许删除旧节点”加强为“必须保留旧节点”。未知函数 `oldSpec` 的定义、不同优先级、任意其他优化目标仍回退。类型化 `MacroObjective.Repair` 可以直接给出 protected edge 集合。

repair 先最大化保留的不同 `(source,target)` 旧边，再最小化展开节点数。同一 binary 的 LEFT/RIGHT 都指向相同旧节点只计一次；有非空 fiber 的边不算保留直接边。

## 当前不支持

binary temporal U、任意 raw Alloy、未识别的 invariant weakening、内部私有 unary identity、任意路径长度/FO 类型、任意目标。reason 包括 `BINARY_TEMPORAL_UNTIL_REQUIRED`、`BINARY_BUDGET_MISSING`、`UNKNOWN_CUSTOM_ALLOY_CONSTRAINT`、`PROTECTED_IDENTITY_NOT_RESOLVABLE`、`UNSUPPORTED_OBJECTIVE`、`UNSUPPORTED_BACKEND`、`INVALID_BUDGET`、`INVALID_TRACE`。

本阶段未做全量论文 benchmark，也不作性能或 speedup 声明。
