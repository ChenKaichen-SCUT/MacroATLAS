# Frozen experimental inputs

Manifests identify every instance by relative task path and SHA-256. They are the
source of the per-instance bounds; the runner does not infer new bounds or
regenerate inputs. `scripts/check_results.py` verifies all input hashes.

| Directory | Cases | Purpose |
| :--- | ---: | :--- |
| `benchmark/` | 623 | Adapted U-free inputs used for the matched experiments |
| `original/` | 623 | Original counterparts, retained to audit preprocessing |
| `small/` | 1,000 | RQ1: eight constraint families, 125 instances per family |
| `unary/` | 12 | RQ4: certified unary depths 4, 6, 8, 10, 12, 14, 16, 20, 24, 28, 32, 40 |
| `discussion/` | 11 | Six certified binary cases and five neutral-profile cases |

The small families are plain, NNF, CNF, DNF, required proposition, no DAG reuse,
global propositional shape, and repair. The final correctness evidence uses the
independent SMT oracle; historical exhaustive-oracle columns in the raw table
are retained for audit and are not substituted for the final reference.

## Benchmark manifest

`benchmark/manifest.csv` stores the task, family, constraint category, B, b,
translation scope, constraint-state count, and original/adapted input hashes.
There are 485 unconstrained and 138 constrained instances. The constrained
families contain 30 Peterson, 20 Robot, 10 Voting, and 78 Weakening instances.

The `b=2` subset has 584 instances; the 39 weakening-consequent instances use
`b=3`. Every method uses the same bounds for a given input. Frozen adapted traces
retain the original constraints; see the English
[constraint audit](../results/evidence/constraints/constraint_profiles.csv).

`select_translation_scopes.py` reproduces the original deterministic selection:
the stratified 200-case selection followed by its 423-case complement. The
selected expanded-size bound is stored per task, and is shared by both methods.

## Trace format

Trace files contain labeled positive/negative lasso traces, the available operator
alphabet, the bound, an expected formula when supplied, and an optional custom
Alloy constraint block. `method/src/main/kotlin/cmu/s3d/ltl/samples2ltl/TaskParser.kt`
defines parsing. Inspect an existing input rather than treating comments or
expected formulas as extra constraints.

Unary and binary manifest certificates state the lower-bound construction.
The five profile inputs have the same learning task and vary only the neutral
profile-state marker. They belong to the discussion controls, not the unary RQ4
curve. No early exploratory instances are included.
