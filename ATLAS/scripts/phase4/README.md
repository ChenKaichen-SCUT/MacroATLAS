# Phase 4 experiment tools

Run from `ATLAS/` on Linux amd64. Install Java, Maven, Python 3.10+, GNU time and
`python3 -m pip install -r scripts/phase4/requirements.txt`.
Use the same JVM, solver, heap, CPU affinity and timeout for both methods.

| Script | Purpose |
| --- | --- |
| `artifact_audit.py` | Verify the official Zenodo download, benchmark bytes and historical workload provenance |
| `correctness_gate.py` | Run all regressions on a clean commit; certify the actual compiled application and dependencies |
| `prepare.py` | Inventory inputs, preserve originals, create U-free copies and obtain support lists from the real analyzer |
| `run.py` | Serial one-JVM-per-task execution, timeout/process cleanup, RSS sampling, immutable batch manifests |
| `validate_results.py` | Reject missing/duplicate runs, verification failures, objective/domain mismatches and changed raw records |
| `analyze.py` | Rebuild performance/encoding/repair tables, failure lists and PDF plots from validated raw data |
| `synthetic.py` | Generate deterministic labelled lassos and parameter sidecars; 55 prespecified default tasks |
| `select_runs.py` | Explicitly select common-solved or stratified follow-up tasks, preserving selection provenance |
| `campaign.py` | Plan isolated parallel workers, install a systemd controller, resume, monitor, merge and archive |
| `isolation.py` | Verify CPU sibling allocations, cgroup memory/swap limits and kernel OOM evidence |
| `full_paper_split.py` | Verify identical matched paper inputs and split the full E4 workload into b=2 and b=3 campaigns |
| `resource_monitor.py` | Persist sampled cgroup memory, OOM and disk use and summarize observed peaks |

Start with:

```bash
python3 scripts/phase4/correctness_gate.py
python3 scripts/phase4/prepare.py --output generated/official --b 2
python3 scripts/phase4/run.py --suite original --root benchmark \
  --tasks generated/official/paper_tasks.txt --timeout 180
python3 scripts/phase4/run.py --suite matched --root generated/official/matched_u_free \
  --tasks generated/official/matched/supported_tasks.txt --b 2 --timeout 180 --repeats 1
```

Read [the full protocol](../../docs/phase4/EXPERIMENT_PROTOCOL.md) before formal runs,
especially the distinctions between Original ATLAS, ATLAS-B and AUTO fallback.
Use `--pilot` for labelled development checks; `--limit` is pilot-only.
Outputs must use a new directory. Result batches and generated inputs are ignored by
Git; archive formal batches separately with hashes. The committed preflight summaries
are resource/functional evidence, not performance claims.

For the user's parallel server deployment, follow
[SERVER_DEPLOYMENT.md](../../docs/phase4/SERVER_DEPLOYMENT.md).
For the replacement server and complete paper workload, use
[FULL_RUN_HANDOFF.md](../../docs/phase4/FULL_RUN_HANDOFF.md).
This explicitly amends the original serial protocol; CPU/memory isolation cannot
eliminate shared cache, memory-bandwidth or cloud-host interference.
`run.py --resume` retains completed results, checks the frozen configuration and
archives unfinished attempts before rerunning them. `java` in new manifests records
the full JVM version, while `javaExecutable` separately records the command path.

For example, after a complete matched batch, explicitly create a repeat subset:

```bash
python3 scripts/phase4/select_runs.py results/COMMIT/MACHINE/BATCH \
  --root generated/official/matched_u_free --output generated/repeats --mode common
python3 scripts/phase4/run.py --suite matched --root generated/repeats/inputs \
  --tasks generated/repeats/analysis/supported_tasks.txt --b 2 --repeats 1
```

The subset result must stay separate from full-workload solved/PAR-2 statistics.
For synthetic tasks, use `--task-budgets` so each JSON sidecar's B/b is applied to
both methods; see [SYNTHETIC.md](../../docs/phase4/SYNTHETIC.md).
