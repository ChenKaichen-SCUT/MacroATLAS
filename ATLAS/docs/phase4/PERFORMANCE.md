# 性能实验状态

旧 commit 的 1/4 单次 pilot 已完成并归档，但它暴露了 constrained coverage、repair scope、parser/translation 和搜索性能问题。该批结果不能代表修复后的算法，也不能与新结果合并。修复内容与定向数据见 [OPTIMIZATION_V2.md](OPTIMIZATION_V2.md)；新 commit 需重新生成输入与计划并完整重跑 1/4 matched。

不从归档 runtime 推导当前 speedup，不将 WSL pilot 与论文机器直接比较，不把 fallback 计入 Macro solved。正式 report 由 `analyze.py` 从通过 `validate_results.py` 的完整 raw CSV 重建，包含 PAR-2、common-solved median/geometric speedup、IQR、四类 solved outcome、memory、encoding 和 repair tuple。

每个 task/repeat 都保留日志和模型。旧服务器批次已打包保存；新结果使用独立目录，完成后再由 `validate_results.py` 和 `analyze.py` 生成正式表格。
