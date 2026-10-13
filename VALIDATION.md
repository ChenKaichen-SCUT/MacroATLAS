# Artifact validation

Validation performed during curation on 2026-10-13. These checks validate the
artifact packaging and executable entry points; they do not replace the frozen
experimental measurements or claim a new full performance campaign.

| Check | Result |
| :--- | :--- |
| Linux Maven build | Successful under OpenJDK 8 in Ubuntu 22.04 |
| Existing Kotlin tests | 111 passed; 0 failures, 0 errors, 0 skipped |
| Independent SMT integration tests | 6 passed with Z3 4.14.1 |
| Input hashes | 623 matched, 623 original counterparts, 1,000 small, 12 unary, 11 discussion controls verified |
| Frozen translation scopes | All 623 matched the deterministic selection script |
| Manuscript statistics | RQ1-RQ4 and discussion-control assertions passed |
| Final learned formulas | 727 SAT formulas matched the saved objectives and verification records |
| Small SMT evidence | 2,589 query hashes and 819 concrete SAT witnesses checked; 1,000 final results present |
| Both-method smoke run | SAT, expanded optimum size 3, output verification PASSED |
| Translation smoke run | ATLAS-B: 38,395 variables / 121,118 clauses; MacroATLAS: 49,172 / 100,564 |
| SMT smoke run | Z3 4.14.1 returned OPTIMAL with size 3 |
| Anonymous package scan | Included text and nested SMT evidence passed the content scan |
| Visualization script | Checked SVGs and Markdown/LaTeX summaries generated successfully |

The smoke input is `5to10Traces/0000.trace`. Its translation counts agree exactly
with the frozen CSV. Smoke runtimes are intentionally not substituted into the
paper results. The historical small-case archive's original solver-version
fields are preserved; fresh SMT validation uses the required 4.14.1 environment.

## Re-run the checks

```sh
sh scripts/build.sh
python3 scripts/check_results.py
python3 datasets/select_translation_scopes.py
python3 scripts/check_witnesses.py
python3 -m unittest discover -s baselines/oracle -p 'test_*.py'
python3 scripts/export_artifact.py --scan-only
```
