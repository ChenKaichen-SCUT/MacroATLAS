# RQ2 same-scope CNF translation data

The 200-case, 400-method-run experiment ran once on `110.41.76.57` at commit `a834e398d2371acace198b4a16c84426a6eaa6da`. It used equal expanded-formula-size bounds for ATLAS-B and MacroATLAS and stopped before MaxSAT solving.

- `plan.json` and `plan.sha256`: frozen case/scope selection, source and binary checksums, resource and time limits.
- `summary/rq2_same_scope_per_run.csv`: all 400 method records, including timeout and translation-error outcomes.
- `summary/rq2_same_scope_paper_data.csv`: all 200 paired cases; ratios only for the 176 pairs in which both translations finished.
- `summary/rq2_same_scope_summary.json`: collector-produced status and ratio summary.
- `analysis.json`: independently recomputed status, scope and stratum analysis from `analyze.py`.
- `../archives/rq2-same-scope-records-20260924.tar.gz`: selected inputs, all 400 model files, started/final records, translator stdout/stderr, plan and logs. Its SHA-256 file is adjacent. Large Kodkod scratch logs and empty WCNF scratch files remain on the original server; they are not needed to reproduce the recorded CNF counts.

Run `python3 analyze.py` from any directory to check the archive against the plan, source table, raw model/translator records, and derived CSVs. See [`RQ2_SAME_SCOPE_RESULTS_2026-09-24.md`](../../../docs/phase4/RQ2_SAME_SCOPE_RESULTS_2026-09-24.md) for the Chinese results report and interpretation.
