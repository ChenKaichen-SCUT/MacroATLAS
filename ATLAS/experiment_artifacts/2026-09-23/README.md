# RQ1 and matched E4 results (23 September 2026)

This directory freezes the first formal RQ1 correctness experiment and the
full, single-run matched E4 comparison. `summarize.py` reads only the saved
CSV/JSON files and reproduces `combined/report.json` and `combined/paired.csv`:

```bash
python3 ATLAS/experiment_artifacts/2026-09-23/summarize.py
cd ATLAS/experiment_artifacts/2026-09-23/archives
sha256sum -c SHA256SUMS
```

No command in this directory launches a solver. The experiment used one
attempt per `(case, method)`; the E4 plans specify `repeats=1`. The archived
RQ1 tiny run contains exactly 3,000 launch markers and 3,000 distinct final
records with `attempt=1`. The E4 merged CSVs contain 1,246 distinct planned
jobs, each with its individual result and command metadata in the archives.

## What was run

| Arm | Server | Source commit | Cases | Methods | Bound and timeout |
| --- | --- | --- | ---: | --- | --- |
| RQ1 tiny exhaustive | `110.41.76.57` | `7c4bef3161415b14b73b78145b5c55c359665044` | 1,000 | exhaustive reference, ATLAS-B, MacroATLAS | U-free; `B=2..4`, `b=0..1`; 180 s per run |
| E4 matched `b=2` | `139.159.185.102` | `0ef52dddff9ea1c4f1d65b34f23e7b528a2f8e9e` | 584 | ATLAS-B, MacroATLAS | matched U-free inputs; 180 s per run |
| E4 matched `b=3` | `139.159.185.102` | `0ef52dddff9ea1c4f1d65b34f23e7b528a2f8e9e` | 39 | ATLAS-B, MacroATLAS | Weakening-consequent matched inputs; 180 s per run |

Each server used seven workers pinned to disjoint CPU sibling pairs
`2,3` through `14,15`. E4 used a 4 GiB JVM heap and 12 GiB worker memory
limit; RQ1 tiny used a 2 GiB JVM heap. The exact Java/solver hashes, input
hashes and commands are in the plans and per-run artifacts. E4 compares two
algorithms on the **same matched input and search bounds**. It is not a run
of the unadapted Original ATLAS artifact, and its U-free restriction and
binary-node bounds must accompany any claim based on it.

## RQ1 correctness

The primary tiny dataset has 1,000 byte-distinct inputs, 125 each of plain,
NNF, CNF, DNF, RequiredProp, NoDAGReuse, global-propositional template and
repair. The exhaustive reference and both learners agree on all 1,000 bounded
SAT/UNSAT outcomes: **819 SAT, 181 UNSAT**. There are **zero status or optimal
objective disagreements**, zero unresolved runs, and all 819 SAT outputs from
each learner passed the independent verifier. Ordinary tasks compare the
minimum formula size; repair tasks compare the full lexicographic
`(kept old edges, final formula size)` objective. A bounded UNSAT result is
about the recorded `B`, `b` and alphabet, not unrestricted LTL learning.

On the official E4 matched inputs there is no exhaustive oracle. For the
**331/623 cases where both algorithms returned SAT or UNSAT**, their statuses
and objective tuples agree, with zero disagreements. The other **292 cases
are unresolved comparisons** because at least one method timed out or
errored; they are not counted as agreements. Across both methods, all 727 SAT
runs passed verification. Thus the E4 evidence extends consistency to the
resolved matched subset, while the tiny arm supplies the independent
optimality oracle. Neither arm proves correctness for all instances.

## E4 performance

| Batch | Method | SAT | UNSAT | TIMEOUT | ERROR | Solved | PAR-2 (s) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `b=2`, 584 cases | ATLAS-B | 316 | 3 | 251 | 14 | 319 | 177.59 |
| `b=2`, 584 cases | MacroATLAS | 345 | 9 | 230 | 0 | 354 | 158.64 |
| `b=3`, 39 cases | ATLAS-B | 27 | 0 | 12 | 0 | 27 | 120.10 |
| `b=3`, 39 cases | MacroATLAS | 39 | 0 | 0 | 0 | 39 | 23.97 |
| **All 623** | **ATLAS-B** | **343** | **3** | **263** | **14** | **346** | **173.99** |
| **All 623** | **MacroATLAS** | **384** | **9** | **230** | **0** | **393** | **150.21** |

MacroATLAS solved **47 more cases** overall. Of 623 paired cases, both
solved 331, only MacroATLAS solved 62, only ATLAS-B solved 15, and neither
solved 215. PAR-2 here uses the measured wall time for SAT/UNSAT and a
`2 × 180 = 360 s` penalty for TIMEOUT/ERROR. The 14 ATLAS-B errors in the
`b=2` batch report Alloy translation-capacity failures; they are unsolved,
not UNSAT.

On the 331 jointly solved cases, the median ratio
`ATLAS-B wall time / MacroATLAS wall time` is **1.25**, with geometric mean
**1.22**. The batches behave differently: the `b=2` median is **1.37** on
304 jointly solved cases; the `b=3` median is **0.31** on 27 jointly solved
cases, meaning MacroATLAS was slower there when both finished. MacroATLAS
nonetheless solved the remaining 12 `b=3` cases that timed out for ATLAS-B,
so its `b=3` PAR-2 is much lower. With one run per job, these are observed
outcomes rather than estimates of run-to-run variation.

## Files and provenance

- `rq1-tiny/`: dataset manifest, frozen plan, gate, per-run CSV and summary.
- `rq1-official/`: 623 paired E4 cases, decisive/unresolved classification and
  source plan/raw SHA-256 values.
- `e4-b2/`, `e4-b3/`: plans, expected jobs, merged raw CSV, derived analyses
  and correctness gates. The individual worker artifacts and exact input
  bytes are in the matching compact archive.
- `combined/`: reproducible counts and one-row-per-case paired CSV.
- `archives/`: all raw input and result files, logs and metadata, compressed
  **without duplicate `source.bundle` files**. The Git commits above contain
  the code; `archives/SHA256SUMS` checks these compact packages.

Byte-for-byte **complete** original archives, including `source.bundle`,
are retained locally at
`/mnt/Space1/MacroATLAS-migration-20260923/archives/` as
`rq1-tiny-primary-1000-20260923.tar.gz`,
`full-e4-b2-20260923.tar.gz`, and `full-e4-b3-20260923.tar.gz`, each with
its `.sha256` file. They also remain under `/srv/macroatlas/archives/` on
their respective source servers. The compact Git archives are separately
hashed and should not be compared against the complete archive checksums.
