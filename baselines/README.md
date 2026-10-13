# Comparison methods

| Directory | Method | Use in this artifact |
| :--- | :--- | :--- |
| `atlas/` | Original ATLAS | Upstream learner and solution extraction; retained for provenance and compatibility |
| `atlas_b/` | ATLAS-B | Explicit syntax-DAG baseline with the same adapted alphabet, structural constraints, B/b bounds, and objective as MacroATLAS |
| `oracle/` | Independent SMT oracle | Finite-DAG encoding in Z3 4.14.1; independent concrete lasso/constraint witness verification |

ATLAS-B and MacroATLAS share the input parser and AlloyMax/Open-WBO backend.
ATLAS-B encodes the explicit DAG. It does not invoke MacroATLAS's fiber encoding.
The experiment entry point selects `atlas-b` or `macro` explicitly; the reported
comparison does not use automatic fallback to the original unbounded learner.

The SMT oracle imports neither learner. It checks exact sizes in increasing
order, establishes UNSAT at all smaller sizes, and checks a satisfying witness
at the optimum. For benchmark repair cases it requires the maximum possible
retention of old edges; failure to find that maximum does not establish UNSAT
for the unrestricted repair objective. The small repair cases enumerate the
retention objective in descending order before minimizing size.

## Reproduction

```sh
python3 scripts/run_experiments.py --suite benchmark --methods atlas-b --output runs/atlas-b
python3 scripts/run_experiments.py --suite benchmark --kind oracle --limit 1 --output runs/oracle-smoke
python3 -m unittest discover -s baselines/oracle -p 'test_*.py'
```

The SMT dependency is fixed to `z3-solver==4.14.1.0`, whose runtime version is
`4.14.1`. The runner rejects other versions. See the root reproduction guide for
full campaigns, deadlines, historical evidence, and solver-independent checks.
