# 性能实验状态

**正式结果尚未运行。** 当前完成实现、正确性/覆盖审计和用于资源规划的小规模 pilot。服务器确认后按 EXPERIMENT_PROTOCOL 执行 Original、matched、AUTO、synthetic 与重复测量。

不从归档 runtime 推导当前 speedup，不将 WSL pilot 与论文机器直接比较，不把 fallback 计入 Macro solved。正式 report 由 `analyze.py` 从通过 `validate_results.py` 的完整 raw CSV 重建，包含 PAR-2、common-solved median/geometric speedup、IQR、四类 solved outcome、memory、encoding 和 repair tuple。

每个 task/repeat 都保留日志和模型。大体量目录位于忽略的 `ATLAS/results/`，待服务器运行后打包归档并登记 URL/checksum；当前未声称不存在的外部下载位置。
