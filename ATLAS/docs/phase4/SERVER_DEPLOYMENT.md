# 并行服务器部署与数据保存

> 本页记录旧服务器的部署路径和命令。新服务器及完整论文任务的准备入口见
> [全量实验交接说明](FULL_RUN_HANDOFF.md)；不要直接在新机器上使用下文固定的旧路径。

当前运行协议每个阶段、每个任务/算法只运行一次，新计划使用 `phase4-once`；旧三次计划冻结保留。

需要先试跑原论文的 1/4 分层子集时，见 [QUARTER_PILOT.md](QUARTER_PILOT.md)。

## 已部署服务器配置

服务器：`110.41.76.57`，Ubuntu 22.04、KVM、Xeon Gold 6266C，12 个可见逻辑 CPU、
6 组 SMT sibling cores、约 93 GiB RAM。用户已将云盘扩容至 120 GB，部署时同步扩展 ext4 文件系统。
固定 Temurin 8u462、Maven 3.6.3、Python 3.10、matplotlib 3.10.9、bundled OpenWBOWeighted。

5 个 worker 分别使用 CPU `2,3` / `4,5` / `6,7` / `8,9` / `10,11`；CPU `0,1` 留给系统。
每个 worker 硬内存上限 16 GiB，禁用 swap，JVM heap 4 GiB，ActiveProcessorCount=2。
总内存预算 80 GiB，保留约 13 GiB 系统余量。低于 8 GiB 磁盘可用空间即停止，结果可恢复。

登录后简短命令：

```bash
macroatlas run       # 启动或继续
macroatlas tail      # tail -F 所有 worker 和总控日志；Ctrl-C 只退出查看
macroatlas status    # 完成数、各状态、剩余磁盘
macroatlas summary   # 全部完成后完整验证、表格与 PDF
macroatlas stop      # 暂停并保留结果
macroatlas backup    # 暂停或完成后打包并生成 SHA256
```

结果根目录 `/srv/macroatlas/experiments/phase4-once`，源码 `/srv/macroatlas/repo-encoding-fix`。
该服务器 5-worker 小样例运行已通过，内核 OOM 分类、停止后恢复、磁盘保护均有独立预检证据。
这些预检不作为正式性能数据；正式正确性证书在最终干净提交上重新生成。

用户本次明确要求尽量并行、避免资源竞争，因此本协议覆盖原实验指引第 36 节的串行要求。
算法和支持范围不变。论文报告必须说明实际采用的是隔离 worker 的并行环境。
CPU affinity/cpuset 和内存硬限制避免 CPU 超额分配与内存超卖；共享 LLC、内存带宽、SSD
以及云主机宿主机干扰无法完全消除，不声称并行耗时等价于完全空载串行耗时。

## 隔离与公平性

- `campaign.py` 读取 Linux 可见 CPU sibling groups；不把同一可见物理核的 SMT siblings 分到不同 worker。
- 至少预留一组核给系统、监控与控制器，各 worker 分到相同数量的核组；同时受 cpuset 和 affinity 限制。
- 根据实测 RAM 设定 worker 数量，所有 worker 的 MemoryMax 总和加系统预留不超过 RAM。
- systemd/cgroup v2 为每个 worker 设置相同 MemoryMax、MemorySwapMax=0。每个 worker 串行运行一个 JVM/native solver 任务。
- 同一 task 的两种方法和全部 repeats 固定分配给同一 worker，顺序由固定 seed 打乱。
- JVM heap、ActiveProcessorCount、180 秒超时和 OpenWBOWeighted 对双方相同。
- 保存每题前后 `memory.events`、cpuset、CPU/IO/pressure 等证据，只有内核 `oom_kill` 增加才归为 `ERROR/CGROUP_OOM`。
- 每两秒检查磁盘剩余空间；默认低于 8 GiB 则停止整批任务并保留现场。扩容后使用同一启动命令继续，不能将存储中断当成 solver timeout。
- 控制器持有全仓库互斥锁；通过注册和 cgroup 核查的 worker 才能使用单独的 worker 锁。

阶段依次为 Original 论文任务、matched、AUTO 全工作负载、synthetic（含安全配置对照）。
一个阶段全部完成并验证后再进入下一阶段；任何 verifier failure 或目标不一致立即停止整批 worker。

## 安装和冻结

服务器需要原生 Ubuntu 22.04 amd64、systemd/cgroup v2、root 部署权限、固定 JDK、Maven、
Python 3.10+ venv、GNU time 和 matplotlib。源码使用独立的冻结 checkout，不在运行期间 pull/build。

```bash
cd /srv/macroatlas/repo-encoding-fix/ATLAS
/srv/macroatlas/venv/bin/python scripts/phase4/correctness_gate.py
/srv/macroatlas/venv/bin/python scripts/phase4/prepare.py --output generated/server-official --b 2
/srv/macroatlas/venv/bin/python scripts/phase4/synthetic.py --output generated/server-synthetic
/srv/macroatlas/venv/bin/python scripts/phase4/prepare.py \
  --root generated/server-synthetic --output generated/server-synthetic-ready --b 2
```

建立 plan 时才依据服务器资源确定 `--workers`、`--memory-mb`。例如足够内存的机器：

```bash
/srv/macroatlas/venv/bin/python scripts/phase4/campaign.py plan \
  --official generated/server-official --synthetic generated/server-synthetic-ready \
  --output /srv/macroatlas/experiments/phase4-once --controller-unit macroatlas-phase4-once --workers 3 --memory-mb 16384 --repeats 1
/srv/macroatlas/venv/bin/python scripts/phase4/campaign.py install-service \
  /srv/macroatlas/experiments/phase4-once
```

以上 workers 数只是示例，必须以实际 RAM 和拓扑审核后的 plan 为准。安装 service 不会自动启动正式实验。
正式启动前使用独立 pilot campaign 对真实 systemd 限额、OOM 分类、完整结果合并及断点恢复做功能检查。

## 运行、实时查看、汇总

```bash
# 开始；已中断时使用同一命令继续。退出 SSH 不会停止实验。
systemctl start macroatlas-phase4-once

# 总控进度与每题结果
tail -n 30 -F /srv/macroatlas/experiments/phase4-once/logs/controller.log \
  /srv/macroatlas/experiments/phase4-once/logs/*-w*.log

# 随时可用：只展示当前完成数，不把未完成批次当作正式结论
/srv/macroatlas/venv/bin/python /srv/macroatlas/repo-encoding-fix/ATLAS/scripts/phase4/campaign.py \
  status /srv/macroatlas/experiments/phase4-once

# 全部完成后：检查完整性并重建表格和 PDF 图
/srv/macroatlas/venv/bin/python /srv/macroatlas/repo-encoding-fix/ATLAS/scripts/phase4/campaign.py \
  summarize /srv/macroatlas/experiments/phase4-once

# 暂停；正在求解的任务会在下次启动时重新运行，已完成题不会重跑
systemctl stop macroatlas-phase4-once
```

## 保存与恢复

Campaign 根目录保存不可变 `plan.json` 与 checksum、源代码 `source.bundle`、精确输入 `inputs.tar.gz`、
正确性证书及完整构建日志。每题保存 command/input hash、stdout/stderr、模型、解和验证结果、
耗时、RSS 和 cgroup 证据。`raw.csv` 和 JSON 使用原子替换、写盘同步；各 worker 的日志不覆盖。
汇总结果位于 `<phase>/merged/processed/`，合并严格核对全部 expected task/variant/repeat。

恢复运行必须匹配原 commit、JVM、编译后应用/依赖 hash、输入 hash 和所有运行参数。
未完成目录移入 `interrupted/` 保留，之后在新目录重跑该题。已记录 TIMEOUT/OOM 是完成的实验结果，
不能偷偷重跑直到成功。correctness failure 必须修复后重新冻结并建立新批次，旧性能数据不混入。

在完成或暂停后归档（拒绝对仍在写入的 campaign 做不完整快照）：

```bash
/srv/macroatlas/venv/bin/python /srv/macroatlas/repo-encoding-fix/ATLAS/scripts/phase4/campaign.py archive \
  /srv/macroatlas/experiments/phase4-once --output /srv/macroatlas/archives/phase4-backup.tar.gz
cd /srv/macroatlas/archives
sha256sum -c phase4-backup.tar.gz.sha256
```

再从本地用 `scp root@服务器IP:/srv/macroatlas/archives/phase4-backup.tar.gz* ./` 保存第二份。
凭据不写入仓库、manifest、命令日志或归档。完整 raw data 不提交 Git；归档和 SHA256 用于长期保存。
