# MacroATLAS

**Anonymous research artifact** for *MacroATLAS: Constraint-Preserving Semantic
Quotient Compilation for Constrained LTL Learning*.

MacroATLAS learns constrained LTL formulas by compiling a macro skeleton and
constraint-preserving unary fibers to the AlloyMax backend. This artifact provides
the implementation, matched baselines, frozen inputs, and the evidence underlying
the final manuscript. The experimental results are included; running the full
experiments is optional.

## Start here

| Review goal | Entry point |
| :--- | :--- |
| Inspect the paper's results | [Results and paper-to-file map](results/README.md) |
| Understand the implementation | [Method and code walkthrough](method/README.md) |
| Inspect the comparison methods | [Baselines](baselines/README.md) |
| Inspect input selection and bounds | [Datasets](datasets/README.md) |
| Recompute every reported statistic | `python3 scripts/check_results.py` |
| Build and run a small example | [Quick start](#quick-start) |
| Replay each experiment | [Reproduction guide](REPRODUCING.md) |

## Repository structure

```text
method/                    MacroATLAS, shared backend interfaces, and tests
baselines/
  atlas/                   Original ATLAS learner
  atlas_b/                 Matched explicit-DAG baseline used in the paper
  oracle/                  Independent finite-DAG SMT encoding and verifier
datasets/
  benchmark/               623 frozen U-free matched benchmark inputs + manifest
  original/                Corresponding original benchmark inputs
  small/                   1,000 frozen correctness inputs + manifest
  unary/                   12 certified unary-growth inputs + manifest
  discussion/              6 binary controls and 5 profile controls + manifests
results/
  raw/                     Final per-instance evidence for RQ1-RQ4
  summary/                 Recomputed summary CSVs
  figures/                 Final manuscript figure SVGs
  discussion/              Evidence for the discussion controls
  evidence/                Constraint audit, SMT checks, and source integrity
scripts/                   Build, replay, consistency checks, and visualization
lib/                       Shared AlloyMax JAR and Linux Open-WBO executable
Dockerfile                 Linux build and runtime environment
pom.xml                    One Maven module compiling both representations
requirements.txt           Python dependencies, including Z3 4.14.1
```

## Quick start

### 1. Verify the published numbers (no solver required)

From the artifact root, with Python 3.10 or later:

```sh
python3 scripts/check_results.py
python3 datasets/select_translation_scopes.py
```

The check reads the frozen inputs and CSVs, verifies input hashes, recomputes all
table entries, and asserts the manuscript's values. Expected last line:
`ALL MANUSCRIPT CONSISTENCY CHECKS PASSED`. It does not replace missing values
with zero or treat TIMEOUT as a solved instance.

### 2. Build on Linux, including tests

Recommended: Docker on an x86-64 machine. Allow at least 8 GB of Docker memory
for the build and smoke runs. Initial image construction requires network access
for Ubuntu packages and public Maven/Python dependencies.

```sh
docker build -t macroatlas-artifact .
docker run --rm --init macroatlas-artifact
```

The image contains OpenJDK 8, Maven, AlloyMax 1.0.3, Open-WBO, and Z3 4.14.1.
The native solver is a Linux x86-64 executable. For native Linux installation and
resource details, see [REPRODUCING.md](REPRODUCING.md).

### 3. Run both learning methods on one input

```sh
docker run --rm --init macroatlas-artifact \
  python3 scripts/run_experiments.py --suite benchmark --limit 1 \
  --output /tmp/smoke
```

Both methods should return SAT on `5to10Traces/0000.trace`, with optimal expanded
size 3 and successful output verification. Timing depends on the machine.
The runner writes `observations.csv` and per-case formulas, verification records,
and metadata. To retain output, mount an output directory as described in the
reproduction guide. Every output directory must be new.

## Experimental scope

| Question | Inputs | Evidence |
| :--- | ---: | :--- |
| RQ1: correctness against the independent SMT oracle | 1,000 small; 623 benchmark | 1,000/1,000 and 393/393 jointly decisive status agreements |
| RQ2: CNF encoding size and translation success | 623 benchmark; 573 complete pairs | Unique-task variable/clause ratios and method-level success counts |
| RQ3: solving performance | 623 benchmark | 346 solved by ATLAS-B; 393 by MacroATLAS |
| RQ4: unary structural growth | 12 certified inputs | 5 solved by ATLAS-B; 12 by MacroATLAS |
| Discussion: binary growth and profile overhead | 6 + 5 certified controls | Separate from the RQ4 unary series |

These entries summarize the stored evidence. Full-precision values and the
comparison denominators are available in [results/](results/README.md).
Earlier exploratory campaigns and obsolete result presentations are excluded.

## Anonymous distribution and provenance

The artifact files contain no author names, affiliations, personal contact links,
machine names, or author-specific absolute paths. Third-party package names and
attributions are retained in [THIRD_PARTY.md](THIRD_PARTY.md).

For anonymous review, distribute the generated `macroatlas-anonymous.zip` through
the venue's anonymous artifact channel. A named hosting account and Git commit
history are outside the content-level anonymization boundary. The export command
in [REPRODUCING.md](REPRODUCING.md) excludes `.git`, local runs, caches, and build
products.

The cleanup relocates source files and updates test/resource paths and build
configuration; it does not modify the learning algorithms or reported measurements.
Frozen source and data hashes are retained in
[source_integrity.json](results/evidence/source_integrity.json). Environment and
historical-record qualifications are documented in the reproduction guide.
