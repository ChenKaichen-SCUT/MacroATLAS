# RQ2 encoding compression experiment

RQ2 uses exactly the same 623 matched U-free E4 cases, with the same `B`, `b`, traces, constraints and objective for ATLAS-B and MacroATLAS. It does not launch either learner again. The completed E4 archives are immutable inputs. For runs that already reported CNF variables and clauses, the collector reuses those records. For missing counts (usually E4 TIMEOUT/ERROR), it translates the Alloy models saved by that one E4 run and throws from Alloy's pre-solve `A4Reporter.solve` callback. This records primary/total Boolean variables and total CNF clauses without invoking SAT search.

Each `(case, method)` produces one RQ2 record. A reused E4 metric has zero new translation attempts. A missing metric has at most one RQ2 job, which translates each distinct saved model once within a 180-second total budget. A started job without a final record is marked `INTERRUPTED_UNRECORDED` and is never relaunched automatically. Seven workers use disjoint CPU sibling pairs 2,3 through 14,15, reserving 0,1. A job can end in `TRANSLATED_ONLY`, `TIMEOUT`, `TRANSLATION_ERROR`, `SOURCE_CHANGED` or `INTERRUPTED_UNRECORDED`; incomplete counts stay blank in the paper table.

The final `summary/rq2_paper_data.csv` has one row for each of the 623 matched instances: identity and input hash; `B`, `b`, `p`, `K`, `B/K`; AP and trace counts/lengths; constraint features and repair flag; `q`, catalog and encoded fiber counts; selected fibers, representative lengths, active anchors/edges when a SAT assignment exists; both algorithms' model bytes, primary/total Boolean vars, total CNF clauses, and paired ratios; E4 outcome/runtime; metric source/status; and model SHA-256s. `summary/rq2_per_run.csv` has one row per method, and `summary/rq2_summary.json` gives completeness and median/p25/p75/min/max distributions. Solver-dependent selected structures are blank for UNSAT/TIMEOUT, never interpreted as zero. AlloyMax 1.0.3's reporter exposes *total* clauses but not a trustworthy hard/soft split, so those columns remain blank rather than invented. The model-byte ratio remains available even when translation fails.

The ratios are for the maximum CNF counts among models actually attempted by each adaptive search path. They measure the observed E4 encoding workload, not a fixed full-`B` formula for every task. CNF ratios are reported only where both counts exist, with the denominator and missingness disclosed. The final CSV also carries the E4 result/time so RQ2 compression can be paired with RQ3 performance.

After planning and service installation on 110.41.76.57:

```bash
macroatlas-rq2 run
macroatlas-rq2 status
macroatlas-rq2 watch
macroatlas-rq2 tail
macroatlas-rq2 summary
```

`run` refuses to relaunch a completed campaign. `status` shows `RQ2 cases XXX/623` plus per-method counts. `summary` reads saved records only and never launches translation or SAT.
