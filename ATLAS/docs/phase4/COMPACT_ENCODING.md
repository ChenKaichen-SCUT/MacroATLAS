# Macro 编码内存修复

## 原因与等价改写

旧实现为每个样本的每个位置建立独立 Pos 原子，并逐位置、逐 fiber 语义类型展开
F/G/FG/GF 布尔表达式。相同的轨迹形状被重复展开，FG/GF 还嵌套枚举 future 集。
这同时增加模型文本、解析树和 Alloy 关系 universe 的大小；并非都属于 SAT 搜索困难。

新实现：

1. Pos 只表示轨迹内的位置，个数为最长轨迹长度。每条轨迹的 av/ev 是不同关系字段，
   不共享真值；提取赋值时恢复原有全局 offset，继续执行原来的逐位置独立 verifier。
2. 按 `(轨迹长度, 循环起点)` 复用语义谓词，以集合/关系表达 successor、future 和真值。
3. 在非空周期循环上，FG 等价于循环中所有位置满足，GF 等价于循环中存在位置满足，
   与有限前缀和当前位置无关。保留内层否定的极性，不将 FG/GF 混同。
4. 同一轨迹形状上产生相同移位作用的语义分组复用子句。所有 fiber ID、代表词、长度、
   空/非空区别、约束状态转换都保留，分组不改变可选 fiber、成本或搜索域。

B、b、共享 DAG 与受保护节点约束、repair 字典序目标均不变。
Original ATLAS 和 ATLAS-B 的求解实现未修改。原始 artifact 的 Alloy 翻译容量限制
仍作为 Original 的失败结果记录，不通过偷偷修改 baseline 消除。

## 检查与记录

- 原有 96 个 JUnit 测试，包括 243 个 tiny、50 个 repair 和 80 个 matched reference 任务。
- 新增两个测试：真实 OOM 输入的模型规模/解析回归；28 个 fiber 语义、420 个位置与
  独立代表词 oracle 的对照（不同轨迹长度、循环起点、同形状不同真值、否定及各类尾部）。
- `5to10Traces/0075.trace`：旧模型 126,666,739 bytes，新模型 136,074 bytes；
  logical positions 1220，Pos 原子 10。该差异是编码规模，不等同于运行时间加速比。
- 每个 Macro 运行额外保存 `stage.json`，在编码、解析、翻译/求解、赋值提取、解码、
  验证各阶段更新，包含模型大小、已用 heap、解析时间等；超时/OOM 后可以保留最后阶段。
- 修复 systemd 暂停竞态：worker 因 BindsTo 先退出时，若 controller 正在停止，记录
  INTERRUPTED，不误报算法 FAILED。真正运行中的 worker 异常仍停止整批。

正式全量/1/4 批次均保持停止，旧数据和旧 checkout 不原地覆盖。诊断重跑必须另建目录，
标记 pilot，保持 Java 8、4 GiB heap、16 GiB worker 上限、180 秒、2 个逻辑 CPU，
不得把针对已知问题选择的样例当成全量加速证据。
