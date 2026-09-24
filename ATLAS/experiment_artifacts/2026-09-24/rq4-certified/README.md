# Certified RQ4 data

The A/B campaign has 18 cases and 36 ATLAS-B/MacroATLAS runs. The profile campaign has 5 MacroATLAS-only runs. All 41 runs were attempted once on `139.159.185.102`, at source commit `1bc3be5c36f454f9448825296a9f1709d676106d` and a 180-second timeout.

- `ab/`: plan, gate, raw and paper CSVs, paired comparison, summary, and optimum-certificate audit.
- `profile/`: plan, gate, raw and paper CSVs, and profile summary.
- `combined/`: one 41-row paper CSV and a SHA-linked summary.
- `inputs/manifest.json`: fixed design, target optima, and input checksums.
- `analysis.json`: independent checks and derived statistics from `analyze.py`.
- `../archives/rq4-certified-records-20260924.tar.gz`: original trace files, all run folders, logs and above source records. The large source bundle is excluded because the repository contains the exact source commit; its checksum is in `source-bundle.sha256` and the bundle remains on the server.

Recheck the compact data with `python3 analyze.py` from any working directory. The script fails if the archived plans, states, raw runs, combined table, optimum audit, or recorded hashes are inconsistent.
