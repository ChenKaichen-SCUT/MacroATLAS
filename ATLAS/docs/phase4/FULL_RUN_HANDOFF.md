# Full paper experiment: source and server handoff

This repository is the source of truth for the next server. `ATLAS/` is a
normal tracked directory, not a submodule. It contains the paper's ATLAS
implementation, its original `benchmark/` inputs and `benchmark_results/`
tables, the bundled AlloyMax and OpenWBO solver, and the latest MacroATLAS
implementation. The original solver remains available through the Original
mode; the new implementation is selected explicitly. The exact upstream
ATLAS v1.0.2 commit and the relationship between the implementations are
recorded in [UPSTREAM.md](../../UPSTREAM.md).

The v4 solver used on the previous server was clean commit
`115f3062f48455a3cd12797c89588a5a9d91da4c`, tagged
`macroatlas-phase4-v4-experiment`. The
`macroatlas-phase4-full-ready` tag adds full-run task splitting and resource
monitoring without changing that solver. Use the full-ready tag on the new
server and run its correctness gate there before collecting timing data.

## Files that must survive the move

A clone of this repository already includes:

| Path | Purpose |
| --- | --- |
| `ATLAS/src/`, `ATLAS/pom.xml` | Original ATLAS path and current MacroATLAS implementation |
| `ATLAS/benchmark/` | Original benchmark inputs (1,247 tracked `.trace` files) |
| `ATLAS/benchmark_results/` | Paper workload provenance and historical tables |
| `ATLAS/lib/AlloyMax-1.0.3.jar`, `ATLAS/lib/open-wbo` | Exact bundled solver binaries |
| `ATLAS/scripts/phase4/` | Correctness gate, input preparation, fair campaign runner, validation, analysis and resource monitoring |

At v4, the Git tree hashes were `620622f5d18c03a2b42a4b17ccc7febb0f787aeb`
for `benchmark/` and `d43a51b8559bbe9d61f20c0a0d90b73d15c4b555`
for `benchmark_results/`. The AlloyMax jar SHA256 is
`724cd5ed894e8ea2df773654db143fbe13144acd42bda2ed0cf833af72c7ec22`;
the OpenWBO executable SHA256 is
`857c3ef8b626b439ac6f07d497f028de3f29683f9e7777f19afd90bcca461eb1`.
Generated inputs and solver output are intentionally not committed: the
preparation and campaign tools recreate them with checksums and archive the
exact bytes used by each formal run.

For an offline installation, the local transfer directory
`/mnt/Space1/MacroATLAS-migration-20260923/offline` holds Temurin 8u462,
the Maven dependency cache and pinned Python wheels with `SHA256SUMS`.
These files are deployment dependencies, not Git source. A fresh online
installation may download the same versions instead. Earlier experiment
results and old working checkouts are not required on the new server.

## Full paper task split

The official paper workload has 623 tasks. With the current analyzer, all
623 have matched inputs. The 39 `weakening/weaken_consequent/` tasks must be
run with `b=3`; the other 584 form a separate `b=2` matched campaign.
Never interpret a `b=2` bounded UNSAT on the 39 as an unrestricted answer.
Run ATLAS-B and MacroATLAS with the same input, bound, machine and timeout
inside each E4 campaign.

`full_paper_split.py` checks both preparations against the paper task list,
coverage and byte hashes, then writes disjoint lists and a manifest. On the
previous server the expected counts were 584 + 39 = 623 and the matched
input-set SHA256 was
`fbc72bea9ca1cdc3cf6b18519469ced9ae1663ab48c753670c596d1f0c5468e2`.
Regenerate and inspect this manifest on the new server; do not import
timings from the previous machine into a new-machine comparison.

## New-server setup and plan

Use Ubuntu 22.04 x86_64 with systemd/cgroup v2 and no swap. Install Java 8,
Maven 3.6.3, Python 3.10, `python3-venv`, GNU `time` and the pinned
`scripts/phase4/requirements.txt`. See
[SERVER_DEPLOYMENT.md](SERVER_DEPLOYMENT.md) for isolation, durability and
systemd commands. Inspect `lscpu -e=CPU,CORE` before assigning workers:
16 vCPUs corresponded to eight physical-core groups under the previous
server's two-thread topology, but the replacement machine must be checked.

For a full run on that topology, a conservative starting configuration is
seven workers, one core group reserved for system/control, 12 GiB cgroup
limit per worker, 8 GiB system reservation, 4 GiB JVM heap, and at least
60 GB SSD. The campaign planner enforces the memory reservation; this
configuration needs about 96 GB installed RAM. The lower 80 GB estimate
derived from the completed quarter is not a proven bound for unmeasured
full-workload tasks.

From the full-ready tag, with `JAVA_HOME` and the Python environment set:

```bash
cd /srv/macroatlas/repo/ATLAS
python scripts/phase4/correctness_gate.py --output generated/full-gate.json
python scripts/phase4/prepare.py --output generated/full-b2 --b 2
python scripts/phase4/prepare.py --output generated/full-b3 --b 3
python scripts/phase4/full_paper_split.py \
  --b2 generated/full-b2 --b3 generated/full-b3 \
  --output generated/full-paper-split
```

Create independent E3 Original, E4 matched b=2, E4 matched b=3, and optional
E5 AUTO/E8 synthetic campaigns. E3 Original and ATLAS-B must be rerun on the
new machine for a fair full-run time comparison. An E4 b=2 plan looks like:

```bash
python scripts/phase4/campaign.py plan \
  --official generated/full-b2 --phases e4-matched \
  --target-tasks generated/full-paper-split/e4-b2-tasks.txt \
  --matched-variants atlas-b macro \
  --workers 7 --memory-mb 12288 --reserve-memory-mb 8192 \
  --repeats 1 --timeout 180 --seed 20260922 --b 2 --heap 4g \
  --java "$JAVA_HOME/bin/java" --gate generated/full-gate.json \
  --output /srv/macroatlas/experiments/full-e4-b2 \
  --controller-unit macroatlas-full-e4-b2
python scripts/phase4/campaign.py install-service \
  /srv/macroatlas/experiments/full-e4-b2
```

For E4 b=3, use `generated/full-b3`,
`e4-b3-consequent-tasks.txt`, `--b 3`, and a distinct campaign directory
and controller unit. Inspect every plan and run only one formal campaign
at a time. Start `resource_monitor.py run` before the campaign, pointing
`--campaign` to its directory and `--output` outside that directory;
`--interval 30 --until-complete` captures its memory/disk history. Pin
the monitor to the reserved CPU group. After completion, use
`resource_monitor.py summary`, `campaign.py summarize`, and
`campaign.py archive`; verify the generated `.sha256` and copy the
archive off the new server.
