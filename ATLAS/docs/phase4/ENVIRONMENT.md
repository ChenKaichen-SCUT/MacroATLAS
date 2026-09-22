# 实验环境与服务器资源建议

## 原论文与 artifact 条件

本地论文第 VIII 节（PDF 页 9–10）说明：Linux、4-core 3.8 GHz CPU、8 GB RAM、OpenWBO/AlloyMax、每题 180 秒。具体 CPU 型号、是否启用超线程、JVM heap 和完整 OS/kernel 未在该段给出，不自行补造。

官方 [ATLAS README](https://github.com/cmu-soda/ATLAS) 说明测试过 Java 8 与 Ubuntu 22.04，bundled OpenWBO 为 Linux amd64；原 [Zenodo artifact](https://zenodo.org/records/14578202) 提供数据与结果。原 Dockerfile 使用 Java 8；正式 timing 选原生 Linux amd64，避免跨架构模拟。

## 当前预检环境（不作为正式性能环境）

当前是 WSL/Microsoft hypervisor 环境，CPU 报告 Intel Core i7-13700F、16 logical CPUs，可见内存约 29 GiB。预检 JVM 为 OpenJDK 21.0.12，固定 Xms512m/Xmx4g，OpenWBOWeighted，20 秒短窗口，12 GiB 的采样 RSS guard。完整 OS/CPU/JVM/solver checksum 见 preflight 的两个 manifest。

串行执行 7 个 Original 任务与 3 对 matched 任务，仅用于功能/资源预检。没有验证失败；common-solved pair 的目标相同。短窗口内观察到：

| 预检方法/实例 | 进程组采样峰值 |
| --- | ---: |
| Original，5to10Traces/0000 | 约 219 MiB |
| Original，robot/final44 | 约 3.32 GiB |
| Original，weakening_40_10_10 | 约 7.81 GiB（20 秒 TIMEOUT） |
| ATLAS-B，increasingNumVariables/0028 | 约 3.78 GiB（20 秒 TIMEOUT） |
| ATLAS-B，moreDetailedTest/0008 | 约 3.07 GiB（20 秒 TIMEOUT） |
| Macro，moreDetailedTest/0008 | 约 2.70 GiB（20 秒 TIMEOUT） |

这些不是 180 秒完整运行的内存上界，也不是方法间正式比较。一个简单实例中宏路径比 ATLAS-B 慢，说明启动/catalog/编码开销必须纳入报告；不从这 3 对样本推导一般加速结论。

## 建议提供的服务器

| 配置 | 用途与判断 |
| --- | --- |
| **8 个独占物理核、64 GB RAM、200 GB 可用 SSD、Ubuntu 22.04 x86_64** | 推荐；给 native solver、JVM、长 trace/大 B 和 raw artifacts 留余量 |
| 4–8 个独占物理核、32 GB RAM、100 GB 可用 SSD | 可启动实验的紧凑配置；统一限制 JVM/任务内存，重任务可能 OOM/超时，作为结果保留 |
| 8 GB RAM | 不建议：仅 20 秒预检已有整任务峰值接近 8 GiB，尚未含系统余量 |
| GPU | 不需要；实现使用 JVM、AlloyMax、CPU MaxSAT |

优先稳定单核性能、独占资源和原生 amd64，而不是很多共享 vCPU。按指引每次只运行一个 solver task；8 核主要给 JVM/GC/OS 留余量，多核不意味着总实验时间线性缩短。服务器内存是物理余量，公平实验的每任务限制必须双方统一并写入 manifest；建议首先保留原 4 GiB heap，若调整则整批双方重跑。

推荐初始每任务 16 GiB 总内存预算；runner 的 RSS guard 只是近似，若需要严格上限，应在服务器配置相同 cgroup v2 memory.max，并同时记录 memory.events 的 OOM 证据。不能将所有 SIGKILL 都误判为 OOM。

## 时间预算

历史 623 个 ATLAS CSV 的 capped runtime 总和约 11.09 小时，仅作计划参考，不能当作新机器 baseline。硬上限估计（不含每题启动、清理和 verification 余量）：

| 计划 | 全部达到 180 秒时 |
| --- | ---: |
| 原论文 623 例 Original，1 次 | 31.15 小时 |
| 全部 ATLAS 格式 1,109 例 Original，1 次 | 55.45 小时 |
| 支持的 521 例，两种 matched 方法，各 1 次 | 52.10 小时 |
| 同上，各 3 次 | 156.30 小时（约 6.5 天） |
| 全部 1,109 例，Original/AUTO 各 1 次 | 110.90 小时 |
| 55 个 synthetic，两种方法，各 3 次 | 16.50 小时 |

建议预留 1–2 周服务器使用时间，先在服务器做分层预跑再收紧估计。如果只对 common-solved 或预注册分层子集做三次重复，开销可明显减少，但须在报告中声明；完整 workload 的 solved/PAR-2 仍保留。

资源配置属于基于论文、代码和本地短窗口测量的建议，不是保证所有实例都能在给定内存内完成。原始日志见 [Original pilot](preflight/resource-pilot-original-v2.csv) 与 [修复后重新执行的 matched pilot](preflight/resource-pilot-matched-v2.csv)。修复前 matched 测量不用于该表。
