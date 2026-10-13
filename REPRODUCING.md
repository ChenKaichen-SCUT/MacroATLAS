# Reproducing the artifact

All commands run from the artifact root. Stored evidence is read-only input to
analysis. Fresh solver runs go to a new directory and never update `results/raw/`.

## Environment

Recommended platform: x86-64 Linux. The paper reports Ubuntu 22.04, an Intel
i7-13700F, and 96 GB RAM. Timing and timeout outcomes can change on other hardware.
The Dockerfile uses Ubuntu 22.04 and OpenJDK 8. OS security package revisions may
advance; the runtime records `java -version` for each new campaign.

| Component | Version |
| :--- | :--- |
| Kotlin | 1.7.0 |
| AlloyMax | 1.0.3, bundled JAR |
| Open-WBO | 2.1, bundled Linux executable |
| Z3 | **4.14.1**, Python distribution `z3-solver==4.14.1.0` |
| Python | 3.10 or newer |
| Maven | 3.6 or newer |

### Docker

```sh
docker build -t macroatlas-artifact .
docker run --rm --init macroatlas-artifact
```

Docker Desktop on Windows must use Linux containers. Allocate at least 8 GB for
building and smoke tests. For the original 12 GiB per-worker performance memory
budget, allocate more than 12 GiB to the Docker VM and run one worker at a time.
Full SMT replay may require 20 GiB for the two documented memory retries.

### Native Ubuntu 22.04

```sh
sudo apt-get update
sudo apt-get install openjdk-8-jdk-headless maven python3 python3-pip libgomp1 zlib1g util-linux
export JAVA_HOME=/usr/lib/jvm/java-8-openjdk-amd64
export PATH="$JAVA_HOME/bin:$PATH"
python3 -m pip install -r requirements.txt
sh scripts/build.sh
```

The build uses a public Google-hosted Maven Central mirror because some networks
block the standard Central endpoint. `scripts/maven-settings.xml` contains no
credentials or private repository. Removing `-s scripts/maven-settings.xml` from
the Maven command uses the normal public Maven Central endpoint.

## 1. Recompute tables and check the frozen evidence

This takes seconds and requires only Python's standard library:

```sh
python3 scripts/check_results.py --output output/summary
python3 datasets/select_translation_scopes.py
```

Every manuscript check must pass before summary files are written. The script
verifies the 623 + 1,000 + 12 + 11 input hashes, compares RQ1 objective tuples,
deduplicates RQ2 by task, recomputes its ratios from backend counts, checks PAR-2
per row, and confirms all performance and scalability sample sizes.

After installing the Python dependencies, verify all archived small-case query
hashes and independently evaluate all 819 SAT witnesses without SMT solving:

```sh
python3 scripts/check_witnesses.py
```

Regenerate data-equivalent visualizations and tables:

```sh
python3 scripts/plot_results.py --output output/presentation
```

The manuscript's original SVG figures are in `results/figures/`. The script
generates SVGs from the checked CSVs and compact Markdown/LaTeX tables, with the
same observations and statistics. Layout may differ from the manuscript exports.

## 2. Run smoke examples

On native Linux, after building:

```sh
python3 scripts/run_experiments.py --suite benchmark --limit 1 --output runs/smoke-solving
python3 scripts/run_experiments.py --suite benchmark --kind translation --limit 1 --output runs/smoke-translation
python3 scripts/run_experiments.py --suite benchmark --kind oracle --limit 1 --output runs/smoke-oracle
python3 -m unittest discover -s baselines/oracle -p 'test_*.py'
```

The selected case is `5to10Traces/0000.trace`. Expected values:

| Check | ATLAS-B | MacroATLAS |
| :--- | ---: | ---: |
| Solving status | SAT | SAT |
| Expanded optimum size | 3 | 3 |
| Translation variables | 38,395 | 49,172 |
| Translation clauses | 121,118 | 100,564 |

The independent SMT run returns `OPTIMAL` with size 3 under Z3 4.14.1. The
oracle integration suite contains six tests, including parsing all 623 inputs,
125 small plain cases, and one example from each official constraint profile.

### Save Docker outputs

Create an empty directory named `output`, then run:

```sh
docker run --rm --init --memory=12g --memory-swap=12g \
  -v "$(pwd)/output:/output" macroatlas-artifact \
  python3 scripts/run_experiments.py --suite benchmark --limit 1 --output /output/smoke
```

In PowerShell use `-v "${PWD}/output:/output"` and put the command on one line.
Do not mount over `/artifact`; the image already contains its compiled classes
and dependency classpath. Native runs use the local `target/` directory.

## 3. Replay learning and translation experiments

```sh
# RQ1 learners on the 1,000 frozen small inputs (original tiny JVM heap: 2 GiB).
python3 scripts/run_experiments.py --suite small --heap 2g --output runs/rq1-small-learners

# RQ2, both representations at the stored per-instance expanded-size scope.
python3 scripts/run_experiments.py --suite benchmark --kind translation --output runs/rq2

# RQ3, both methods on all 623 inputs, including their recorded B/b bounds.
python3 scripts/run_experiments.py --suite benchmark --output runs/rq3

# RQ4, both methods on all 12 certified unary-growth inputs.
python3 scripts/run_experiments.py --suite unary --output runs/rq4

# Discussion controls (profile runs select MacroATLAS only).
python3 scripts/run_experiments.py --suite binary --output runs/discussion-binary
python3 scripts/run_experiments.py --suite profile --output runs/discussion-profile
```

The runner is serial and starts a fresh JVM for every observation. It records
SAT, UNSAT, TIMEOUT, or ERROR; kills the JVM and native solver process group at
the 180-second wall-clock deadline; and assigns PAR-2=360 to unfinished runs.
The CSV contains measured external wall time and the verifier's status. A timeout
is a censored observation, never a completed 180-second runtime.

RQ2 has separate 120-second emission and 180-second translation limits, matching
the archived campaign configuration. Translation stops in the pre-solve reporter
callback; Open-WBO solving is not included. Repair translation retains hard
constraints and the size objective at the common scope.

The original performance campaign used seven workers pinned to disjoint CPU
sibling pairs, a 4 GiB heap per JVM, and 12 GiB per-worker memory limits. The
portable serial runner keeps the same task semantics, heap, and deadlines but
does not recreate that scheduling history. Use `--cpu <cpu-list>` for explicit
affinity, and a container or cgroup with swap disabled for memory isolation.
`configuration.json` records each replay's settings. Full replay can take hours;
the oracle can take days when run serially.

## 4. Replay independent SMT checks (Z3 4.14.1)

```sh
python3 scripts/run_experiments.py --suite small --kind oracle --output runs/rq1-small-oracle
python3 scripts/run_experiments.py --suite benchmark --kind oracle --output runs/rq1-benchmark-oracle
```

The runner checks the exact runtime version and rejects anything other than
4.14.1. Each query and satisfying witness is saved; the concrete verifier checks
each SMT witness independently of the encoding.

For the small inputs, the per-query timeout is 30 seconds. For benchmark inputs,
the final archived configuration uses 1,500 seconds per SMT query and 4,500
seconds per case, with a 5 GiB address-space limit. Two cases were retried with a
20 GiB limit: `baseTest/0019.trace` and `baseTest/0040.trace`. A single-case replay
can select either input with `--task` and `--oracle-memory-gib 20`.

### Historical evidence qualifications

The final benchmark evidence incorporates resumed and retried campaigns. Their
limits and attempt accounting are retained in `results/evidence/oracle/`.
The manuscript describes the SMT budget as 1,500 seconds per instance; the
archived configuration distinguishes a 1,500-second query deadline from a
4,500-second case deadline. The reproduction commands follow the recorded
configuration and do not relabel earlier attempts as a single run.

The artifact's required SMT version is 4.14.1, consistent with the manuscript.
The stored small-case audit archive contains original records bearing version
4.14.2. Those historical fields are preserved as recorded, not relabeled as
4.14.1. They are not a claim that those historical invocations used the pinned
reproduction environment. New commands and integration tests require 4.14.1.

Large-case evidence includes final per-case results, exact-size check hashes,
and all recorded attempts. Full large-case SMT query/witness payloads are not
present in the supplied repository snapshot; fresh replay emits them. The
small-case query/witness payloads are included in a compact archive. An absent
payload is not represented as an independently replayed proof.

## 5. Export the anonymous package

```sh
python3 scripts/export_artifact.py --output output/macroatlas-anonymous.zip
```

The exporter includes only the documented source, data, results, and setup files.
It excludes Git history, targets, caches, local runs, temporary files, and this
output directory; scans included text and archive contents; and writes a SHA-256
file manifest. Publish the ZIP through an anonymous review channel. A ZIP cannot
make an author-identifying hosting URL or old Git commits anonymous.
