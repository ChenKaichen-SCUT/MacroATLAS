# ATLAS 上游来源

本目录基于以下上游版本：

- 仓库：<https://github.com/cmu-soda/ATLAS>
- 版本标签：`v1.0.2`
- Commit：`f5134d2a3b08e762bf16ebfbd4988a94daa35f88`
- 对应论文：*Constrained LTL Specification Learning from Examples*

原始 `README.md`、`pom.xml`、求解器源码、测试、数据及 `lib/` 文件予以保留。
MacroATLAS 第一阶段新增的实现位于 `src/main/kotlin/cmu/s3d/ltl/macro/`，
新增测试位于 `src/test/kotlin/cmu/s3d/ltl/macro/`。
完整改动与验证说明见 [实现报告](docs/phase1/IMPLEMENTATION_REPORT.md)。

第二阶段在同一 `macro/` 包下新增 `dag/`、`analysis/`、`kernel/`，
用于真实解的 DAG 提取和可验证的 macro 压缩—重建闭环；原求解器源码与依赖版本保持不变。
细节见 [Phase 2 实现报告](docs/phase2/IMPLEMENTATION_REPORT.md)。
同时将 `lib/open-wbo` 在 Git 中的文件模式修正为 `100755`，确保 Linux clone 后可直接执行。

第三阶段新增 `macro/search/`、fixed-template automata 与 CLI 可选 `--macro` 参数。
原 `LTLLearner`、TaskParser、Phase 1/2 源码和 bundled 依赖保持不变。
默认 CLI 仍走原求解路径；详见 [Phase 3 实现报告](docs/phase3/IMPLEMENTATION_REPORT.md)。

第四阶段新增独立 `experiment/` 入口和 `scripts/phase4/` 实验工具。
Original ATLAS 路径继续调用未经修改的原求解器；ATLAS-B 是明确修改边界、目标和
trace successor 编码的实验基线，详见 [实验协议](docs/phase4/EXPERIMENT_PROTOCOL.md)。
Phase 3 宏求解器仅添加统计和验证失败分类，不增加支持范围。

## Git 收录方式

`ATLAS/` 作为普通目录直接收录于
[ChenKaichen-SCUT/MacroATLAS](https://github.com/ChenKaichen-SCUT/MacroATLAS)，
所有源码和新增文件均由根仓库跟踪，没有使用 submodule 或 gitlink。

首次整理本地工作区时，原 `ATLAS/.git` 被完整迁移至
MacroATLAS 根目录的 `.git/upstream-atlas/`，保留原上游提交历史和配置。
这份备份只保存在原工作区的本地 Git 元数据中，不会上传，也不会随新 clone 下载。
新 clone 无需该备份即可构建、测试和开发。

在保有该备份的原工作区中，可从 MacroATLAS 根目录只读查看上游记录：

```bash
git --git-dir=.git/upstream-atlas --work-tree=ATLAS log -1
```

后续改动统一在 MacroATLAS 根仓库提交和推送；不要在 `ATLAS/` 中再次 `git init`。
