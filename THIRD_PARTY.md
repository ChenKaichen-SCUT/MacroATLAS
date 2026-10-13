# Third-party components and provenance

Anonymization concerns this submission's authors. It does not remove attribution
to prior work or rewrite third-party package metadata.

| Component | Role and provenance |
| :--- | :--- |
| ATLAS / LTL-Learning | Original learner, trace parser, and benchmark foundation; upstream project: <https://github.com/SteveZhangBit/LTL-Learning> |
| AlloyMax 1.0.3 | Shared backend, bundled as `lib/AlloyMax-1.0.3.jar`; upstream project: <https://github.com/cmu-soda/AlloyMax> |
| Open-WBO 2.1 | Native MaxSAT solver, bundled as `lib/open-wbo`; upstream project: <https://github.com/sat-group/open-wbo> |
| Z3 4.14.1 | Independent SMT solver installed from the pinned Python requirement; upstream project: <https://github.com/Z3Prover/z3> |
| samples2LTL | Predecessor of the trace format; upstream project: <https://github.com/ivan-gavran/samples2LTL> |

The `cmu.s3d.ltl` package prefix is inherited from the original implementation.
Both learner representations use the same bundled backend binaries. Their
original checksums are included in `results/evidence/source_integrity.json`.

Dependency licenses and notices remain with their distributions. The supplied
repository snapshot did not include a project-wide license for the new code;
this curation does not invent one or relicense third-party materials.
