# 合成数据与参数实验

`scripts/phase4/synthetic.py` 按 prefix formula、seed、B/b、AP、每类 traces 数和 lasso 长度生成 `.trace` 与每例 JSON。独立 Python evaluator 直接遍历 successor/future，支持当前 U-free syntax；不调用 solver/normalizer/fiber。输入 target 的语义只用于标签，不声明它一定是这些有限样本的最小公式。

预定义 55 个任务，覆盖 X-chain 长度 1–30、Boolean-heavy control、B={5,7,9,11,15,21,31}、b={0,1,2,3,4}、p={0,1,2,4,8}、AP={1,2,4,8}、每类 traces={4,8,16,32,64}、长度={4,8,16,32}、profile 配置。正样本数和负样本数还各自独立变化，另一类固定为 8。采用单因素系列，不展开所有参数的笛卡尔积。控制组的允许字母表仅 Boolean。

```bash
python3 scripts/phase4/synthetic.py --output generated/synthetic --seed 20260924
python3 scripts/phase4/prepare.py --root generated/synthetic --output generated/synthetic-ready --b 2
python3 scripts/phase4/run.py --suite matched --root generated/synthetic-ready/matched_u_free \
  --tasks generated/synthetic-ready/matched/supported_tasks.txt --task-budgets --repeats 3
```

`--task-budgets` 从 sidecar 读取每个任务的 B/b，双方保持相同。p 来自 raw protected declaration/identity constraints，经真实 analyzer 确认，不能仅在 metadata 中伪造。

可用 `--target 'G(->(x0,F(X(x1))))' --B 9 --b 1 --ap 2 --traces 8 --length 8` 生成额外的预注册目标，包括 FX^kG、两分支合取及 response。每例正负样本独立求值；样本不足时记录实际数量，无法产生两类则明确报错，不重新标记样本。

默认停止规则：执行所有预注册任务；不根据某方法输赢裁剪规模。若正式预算需要更早停止，应在运行前新增明确协议和任务列表，而非运行后删除 timeout。

上述通用 synthetic suite 的生成与管线已验证。另行预注册并完成的 RQ4
scalability suite 及其结果、限制见 [RQ4 实验结果](RQ4_RESULTS_2026-09-24.md)；
它与此处的通用 suite 是两个不同的数据集。
