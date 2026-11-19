# MacroATLAS

Artifact for *MacroATLAS: Constraint-Preserving Semantic
Quotient Compilation for Constrained LTL Learning*.

MacroATLAS learns constrained LTL formulas by compiling a macro skeleton and
constraint-preserving unary fibers to the AlloyMax backend. This artifact provides
the implementation, matched baselines, frozen inputs, and the evidence underlying
the final manuscript. The experimental results are included; running the full
experiments is optional.

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

### 1. Build on Linux, including tests

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

### 2. Run both learning methods on one input

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
