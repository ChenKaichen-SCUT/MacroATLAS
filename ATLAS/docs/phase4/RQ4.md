# RQ4 scalability protocol

This is a separate synthetic, matched-domain comparison of ATLAS-B and
MacroATLAS. It does not use or alter the official E4 inputs/results, and it
does not compare with unrestricted Original ATLAS.

`scripts/phase4/rq4.py generate` fixes 30 deterministic cases before any
solver outcome is observed. Each case has a `.trace` input and JSON sidecar.
The axes are: `B` (6 favorable cases), unary depth (8), `b` (5), a Boolean
control `B` series (5), constraint state count `q` (4), and two target-shape
checks. All variants use the same input, allowed operators, `B`, `b`, traces,
timeout and objective for each case. The B series and controls reuse a fixed
trace seed within their axis, so only the named size/budget parameter changes.
The favorable regime uses small `b` and long X chains; the Boolean control
has short target unary depth and `K` close to `B`. `q` is varied by adding
required-proposition facts to an otherwise identical task. The separate
`inspect` mode measures actual reachable minimized automaton states at each
case's own `B` and `b`; unsupported tasks or a failed q gradient abort setup.

The target formula is a known labeling witness, **not** proof that its size
or unary depth is optimal for the finite samples. `targetUnaryDepth` is a
generation parameter. Learned formula structure is measured from the actual
solution DAG where available. Likewise, `compressionPotential=1-K/B` is a
structural bound, not observed encoding reduction.

Formal runs use the correctness gate, seven workers on seven disjoint
physical-core sibling groups, 180 seconds and 10 GiB per worker, one repeat,
and `--strict-once`. The last setting records an interrupted started attempt
as `ERROR/INTERRUPTED_PRIOR_ATTEMPT` on resume instead of rerunning it.
Failures remain in the table. An objective/verifier mismatch stops the
campaign; no alternate cases are substituted.

At completion, `rq4_paper_data.csv` contains one row per algorithm/case with
status, wall time, peak RSS, backend variables/clauses and model size (when
available), timing stages, actual `q`, `B`, `b`, `p`, `K`, target and learned
formula structure. `rq4_pairs.csv` contains paired outcomes and speedup only
when both algorithms solved. `rq4_summary.json` includes per-axis status and
solved-time aggregates plus input/result checksums. The campaign also saves
its exact input archive, source bundle, plan, gate, worker logs and individual
job artifacts. See the server's `macroatlas-rq4` command for run/status/tail/
summary/finalize.
