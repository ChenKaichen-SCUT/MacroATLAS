# MacroATLAS implementation

The implementation is Kotlin. Paths below are relative to
`src/main/kotlin/cmu/s3d/ltl/`. Public package names are inherited from the upstream
code and remain unchanged so that moving files does not change behavior.

## Reading order

| Step | Source | Role |
| :--- | :--- | :--- |
| Parse inputs | `samples2ltl/TaskParser.kt` | Parse labeled lasso traces, operator alphabet, bounds, and custom constraints |
| Recognize the supported domain | `macro/search/RecognizedConstraintAnalyzer.kt` | Construct the constraint plan, protected identities, budgets, and objective |
| Classify unary words | `macro/unary/UnaryNormalizer.kt` | Compute the behavior class of a U-free unary word |
| Preserve constraint state | `macro/constraint/` | Constraint automata and their product states |
| Construct fibers | `macro/fiber/FiberTable.kt` | Bounded breadth-first enumeration with shortest representatives |
| Build the macro representation | `macro/kernel/` | Anchors, ports, contraction, canonicalization, and expansion |
| Compile the backend | `macro/search/MacroAlloyModelBuilder.kt` | Macro constraints, lasso semantics, size accounting, and repair objective |
| Optimize | `macro/search/MacroLearner.kt` | Invoke AlloyMax and decode the optimized assignment |
| Validate | `macro/search/FinalSolutionVerifier.kt` | Check the expanded DAG, constraints, budgets, traces, and objective |
| Run an experiment | `experiment/ExperimentMain.kt` | One task per JVM, with explicit method selection and structured output |

## Representation invariants

The fiber key records the input constraint state, behavior class, whether the
word is nonempty, and output constraint state. In particular, the empty word is
distinguished from a nonempty word with the same behavior. Acceptance is checked
at the consumer; intermediate nonaccepting states are not silently discarded.

Protected identities and sharing boundaries stay explicit in the skeleton.
Repair first maximizes retained direct edges and then minimizes expanded DAG
size. The final concrete verifier checks the expanded output, not only the
compressed representation. These invariants are documented in source comments
and exercised by the tests under `src/test/kotlin/`.

The implementation allocates `K = min(B, p + 3b + 2)` anchor slots, as described
in the manuscript's implementation details. The artifact does not replace this
with a tighter theoretical bound.

## Commands

Run `sh scripts/build.sh` from the artifact root. The root Maven module compiles
this source tree together with the two baseline trees and runs the Kotlin tests.
Use `python3 scripts/run_experiments.py --help` for the portable experiment runner.
Shared parser/backend interfaces remain here to avoid divergent copies across
the two methods.
