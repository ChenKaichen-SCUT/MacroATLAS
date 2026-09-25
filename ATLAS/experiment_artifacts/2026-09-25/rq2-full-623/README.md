# RQ2 same-scope full 623-case artifact

This directory contains the completed same-expanded-size-scope CNF translation comparison: the frozen 200 cases from `../../2026-09-24/rq2-same-scope/` plus the 423 complementary cases. Each of ATLAS-B and MacroATLAS was attempted once per case and scope, for 1,246 method records. No MaxSAT solve was invoked. The earlier experiment measuring each algorithm's maximum actual search model is not used in these statistics.

- `plan.json`, `plan.sha256`, `state.json`: frozen complement, input/code/backend hashes, CPU and time limits, completion state.
- `summary/rq2_same_scope_*.csv` and `.json`: new 423-case campaign's 846 runs and 423 pairs.
- `summary/rq2_full_623_*.csv` and `.json`: combined 1,246 method runs and 623 pairs, with ratios only on fully translated pairs.
- `summary/RQ2_FULL_623_REPORT.zh-CN.md`: automatic server report.
- `analysis.json`, `analyze.py`: independent audit of both compact raw archives, source/task coverage, one-attempt markers, input/model hashes, translator callbacks, paired ratios, and summary statistics.
- `../archives/rq2-full-remaining-423-records-20260925.tar.gz` and adjacent `.sha256`: all 423 input snapshots, 846 started/final records, emitted models, translator output, plan, summary, and controller log. The old 200-case archive remains under `../../2026-09-24/archives/`.

Large Kodkod scratch logs and empty WCNF temporary files stay on the server; they are not used to compute the reported CNF counts. Their exclusion reduces the new archive from a 10 GiB working directory to 11 MiB while preserving all source inputs, models, callbacks, records, and summaries needed for audit.

Re-audit locally:

```bash
python3 ATLAS/experiment_artifacts/2026-09-25/rq2-full-623/analyze.py
```

See [Chinese analysis](../../../docs/phase4/RQ2_FULL_623_RESULTS_2026-09-25.md) for the conclusions and scope limitations.
