# RQ4 follow-up: certified Boolean control and actual size-demand series

The first RQ4 campaign (`rq4-scale-once` on 139.159.185.102) is frozen. Its
Boolean control and binary-budget cases admitted a one-literal optimum, while
the fixed-target B series stopped searching near size 8. This follow-up uses
**thirteen new IDs** under `rq4f_`; no earlier task/method pair is rerun. It runs
only on 110.41.76.57, in a separate worktree and campaign directory.

`scripts/phase4/rq4_followup.py generate` fixes three paired series:

| Series | Cases | Fixed input | Changing quantity |
| --- | --- | --- | --- |
| Favorable unary | `B=7,9,11`, `b=1`, `K=5` | Same 32 lasso traces, one AP, length 16 | Witness `X^(B-1)x0`; actual optimum is checked after solving |
| Boolean control | `B=7,9,11`, `b=3,4,5`, `K=B` | All 64 one-state valuations of six AP | Conjunction of the first 4, 5, 6 variables |
| Fixed-target B | `B=7,9,12`, `b=5` | Same 64 valuations and six-variable conjunction | Only the allowed B; certified minimum size 11, hence bounded UNSAT/UNSAT/SAT |
| Binary budget | `B=21`, `b=5,6,7,8` | Same 64 valuations and six-variable conjunction | Allowed binary budget only; certified optimum stays size 11 |

The Boolean controls have an independent lower-bound certificate: the complete
truth table contains, for every required variable, two valuations differing
only on it and carrying opposite labels. On one-state lassos `X/F/G` are the
identity, so every required variable must occur. Binary fan-in two needs at
least `n-1` binary nodes to combine `n` essential literals; hence the minimum
total size is `2n-1`. The supplied conjunction achieves the bound. This proof
allows a pre-run check that the Boolean cases cannot collapse to a literal.

The favorable series keeps its full trace set constant, including a pulse at
each position and deterministic random traces; increasing `B` also increases
the witness depth. **This is size/depth co-scaling, not a pure fixed-target B
effect.** `rq4f_design_audit.json` checks whether both solvers actually find
size `B` at each point. A timeout leaves that observation unresolved. The
series supports an observed B-demand claim only at SAT points where learned
size and search scope demonstrably increase. The separate fixed-target series
isolates B without changing its formula, trace set, AP or b; the full truth
table proves the SAT/UNSAT threshold. It tests the cost of exploring larger
bounds, although its low-B cases are UNSAT and must not be compared to SAT
runtime as if outcomes were identical.

The two algorithms use identical U-free input, B, b, objective, 180-second
limit and CPU pair for each case. Formal runs require the server's correctness
gate, one repeat and `--strict-once`: interrupted started attempts are
recorded as ERROR and are never rerun. The completed campaign automatically
writes `rq4_paper_data.csv` (26 rows, including status, time, memory, actual
formula structure, B/b/K/q, backend size and proof metadata), `rq4_pairs.csv`,
`rq4_summary.json`, and `rq4f_design_audit.json`. The campaign plan, checksums,
exact inputs, source bundle, logs, and per-run artifacts remain alongside them.

On the server:

```bash
macroatlas-rq4-followup run
macroatlas-rq4-followup status
macroatlas-rq4-followup watch
macroatlas-rq4-followup tail
macroatlas-rq4-followup summary
```
