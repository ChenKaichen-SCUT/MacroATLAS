# RQ1 correctness experiment

The primary tiny batch contains 1,000 generated U-free cases with IDs `tiny_01000`–`tiny_01999` and a fixed seed. Eight profiles are equally represented: unconstrained, NNF, CNF, DNF, RequiredProp, NoDAGReuse, global-propositional template, and repair. Its cases mix deliberate contradictions with satisfiable literal, negation, Boolean, temporal and repair patterns; the exhaustive oracle, rather than the generator, determines the true optimum. Independent smoke cases have IDs starting at 200000 and are excluded. A first exploratory batch (`tiny_00000`–`tiny_00999`) remains archived separately; its generated tasks had a weaker optimum-size distribution and are not used as the primary RQ1 claim. No case appears in both batches, and no completed method/case is rerun.

Every primary case has one exhaustive reference, one ATLAS-B solve, and one MacroATLAS solve. The exhaustive reference enumerates rooted ordered DAGs, including sharing, within each case's B and b. A reference SAT result supplies the minimum rooted size, or the lexicographic repair tuple (maximum kept old edges, minimum size). Each solver's SAT answer is checked against the original positive/negative lasso traces, the recognized constraint automaton and identity constraints. Formula strings are display artifacts; comparisons use `(status, objectivePrimary, objectiveSecondary)`. UNSAT is only a bounded claim under the recorded B, b and U-free alphabet. TIMEOUT, ERROR and interrupted attempts are unresolved, never agreements.

`rq1.py prepare` freezes exact `.trace` bytes and per-case metadata. `plan` requires a clean commit and a passed Phase 4 correctness gate on the machine. It stores the dataset, source bundle, classpath hash, gate, input archive and checksums. `run` pins seven workers to disjoint core sibling pairs, reserving CPU 0,1. A worker runs oracle, ATLAS-B and MacroATLAS sequentially for each assigned case. Every method/case has a separate directory with a launch marker, stdout, stderr, resource log, JVM result, solver files and an atomic outer record. Completed records are skipped on restart. If a started process lacks a final result, it is marked `INTERRUPTED_UNRECORDED` and is not launched again without a new explicit protocol.

Server commands after installation:

```bash
systemctl start macroatlas-rq1-v2
watch -n 5 '/srv/macroatlas/venv/bin/python /srv/macroatlas/repo/ATLAS/scripts/phase4/rq1.py status /srv/macroatlas/experiments/rq1-tiny-v2-1000'
tail -n 20 -F /srv/macroatlas/experiments/rq1-tiny-v2-1000/logs/controller.log
/srv/macroatlas/venv/bin/python /srv/macroatlas/repo/ATLAS/scripts/phase4/rq1.py summary /srv/macroatlas/experiments/rq1-tiny-v2-1000
```

The official benchmark arm reuses the already running E4 matched results from the other server. Do not run those 623 pairs again. After both E4 campaigns finish, transfer both complete campaign archives to this machine and run `rq1.py official --b2 DIR --b3 DIR --output /srv/macroatlas/experiments/rq1-official`. The importer validates exactly 584+39 disjoint paired tasks and reports decisive agreements, objective mismatches, SAT verifier results and unresolved TIMEOUT/ERROR cases. It never treats matched U-free tasks as untouched Original ATLAS inputs.

The tiny per-run CSV contains the RQ1 fields requested in `data.txt`, including B, b, AP and trace counts, status, verification, objective tuple, rooted size, binary/unary counts, unary depth, DAG nodes and sharing. Full backend metadata remains in each JVM `result.json`; the outer `record.json` adds wall time and the attempt identity. Backend hard/soft clause counts are not exposed separately by the current AlloyMax reporter, so these are not invented.
