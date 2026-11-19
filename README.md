# MacroATLAS

Artifact for *MacroATLAS: Constraint-Preserving Semantic
Quotient Compilation for Constrained LTL Learning*.

MacroATLAS learns constrained LTL formulas by compiling a macro skeleton and
constraint-preserving unary fibers to the AlloyMax backend. This artifact provides
the implementation, matched baselines, frozen inputs, and the evidence underlying
the final manuscript. 

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
