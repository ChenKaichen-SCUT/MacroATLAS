#!/usr/bin/env python3
"""Build plotting tables from the archived, one-attempt experiment records."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "result"
ART = ROOT / "ATLAS" / "experiment_artifacts"
E4 = ART / "2026-09-23"
RQ2 = ART / "2026-09-25" / "rq2-full-623" / "summary"
RQ4 = ART / "2026-09-24" / "rq4-certified" / "combined"
ALGORITHMS = {"oracle": "Oracle", "atlas-b": "ATLAS-B", "macro": "MacroATLAS"}
DECISIVE = {"SAT", "UNSAT"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(name: str, rows: list[dict[str, str]], fields: list[str]) -> None:
    assert rows, name
    assert all(set(row) == set(fields) for row in rows), name
    with (OUT / name).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"{name}: {len(rows)} rows")


def unique(rows: list[dict[str, str]], *keys: str) -> None:
    values = [tuple(row[key] for key in keys) for row in rows]
    assert len(values) == len(set(values)), keys


def categorical(family: str) -> str:
    return "constrained" if family in {"peterson", "robot", "voting_machine", "weakening"} else "unconstrained"


def par2(row: dict[str, str], timeout_sec: float = 180.0) -> str:
    return row["totalSec"] if row["status"] in DECISIVE else str(2 * timeout_sec)


def rq1_tiny() -> None:
    source = read_csv(E4 / "rq1-tiny" / "per-run.csv")
    assert len(source) == 3000 and len({r["caseId"] for r in source}) == 1000
    assert Counter(r["method"] for r in source) == {"oracle": 1000, "atlas-b": 1000, "macro": 1000}
    unique(source, "caseId", "method")
    rows = [{"algorithm": ALGORITHMS[r["method"]], **r} for r in source]
    rows.sort(key=lambda r: (r["caseId"], {"oracle": 0, "atlas-b": 1, "macro": 2}[r["method"]]))
    write_csv("RQ1_small_1000.csv", rows, ["algorithm", *source[0]])


def rq1_official() -> set[str]:
    source = read_csv(E4 / "rq1-official" / "per-case.csv")
    assert len(source) == 623
    unique(source, "task")
    rows = []
    for r in source:
        decisive = r["atlasBStatus"] in DECISIVE and r["macroStatus"] in DECISIVE
        assert (r["bothDecisive"] == "True") == decisive
        for algorithm, prefix in (("ATLAS-B", "atlasB"), ("MacroATLAS", "macro")):
            rows.append({
                "task": r["task"], "family": r["family"], "category": categorical(r["family"]),
                "algorithm": algorithm, "B": r["B"], "b": r["b"],
                "status": r[prefix + "Status"], "objectiveKind": r["objectiveKind"],
                "objectivePrimary": r[prefix + "Primary"],
                "objectiveSecondary": r[prefix + "Secondary"],
                "verification": r[prefix + "Verification"],
                "totalSec": r[prefix + "TotalSec"], "bothDecisive": r["bothDecisive"],
                "pairStatusAgreement": str(r["atlasBStatus"] == r["macroStatus"]) if decisive else "",
                "pairObjectiveAgreement": str(
                    (r["atlasBPrimary"], r["atlasBSecondary"])
                    == (r["macroPrimary"], r["macroSecondary"])
                ) if r["atlasBStatus"] == r["macroStatus"] == "SAT" else "",
            })
    unique(rows, "task", "algorithm")
    rows.sort(key=lambda r: (r["task"], r["algorithm"]))
    write_csv("RQ1_official_623.csv", rows, list(rows[0]))
    return {r["task"] for r in source}


def rq2_full(expected_tasks: set[str]) -> None:
    per_run = read_csv(RQ2 / "rq2_full_623_per_run.csv")
    per_case = read_csv(RQ2 / "rq2_full_623_paper_data.csv")
    assert len(per_run) == 1246 and len(per_case) == 623
    assert {r["task"] for r in per_case} == expected_tasks
    unique(per_case, "task")
    unique(per_run, "task", "method")
    assert all(r["attempt"] == "1" and r["solverInvoked"] == "False" for r in per_run)
    paired = {r["task"]: r for r in per_case}
    rows = []
    for r in per_run:
        pair = paired[r["task"]]
        prefix = "atlas" if r["method"] == "atlas-b" else "macro"
        assert r["status"] == pair[prefix + "Status"]
        assert r["vars"] == pair[prefix + "Vars"]
        assert r["backendTotalClauses"] == pair[prefix + "Clauses"]
        rows.append({
            "algorithm": ALGORITHMS[r["method"]],
            "constraintGroup": "constrained" if int(r["qStates"]) > 1 else "unconstrained",
            **r,
            "pairedTranslated": pair["pairedTranslated"],
            "B_over_K": pair["B_over_K"],
            "C_V": pair["C_V"], "C_C": pair["C_C"],
        })
    rows.sort(key=lambda r: (r["task"], r["algorithm"]))
    write_csv("RQ2_translation_623.csv", rows,
              ["algorithm", "constraintGroup", *per_run[0], "pairedTranslated", "B_over_K", "C_V", "C_C"])


def rq3_e4(expected_tasks: set[str]) -> None:
    source = read_csv(E4 / "e4-b2" / "raw.csv") + read_csv(E4 / "e4-b3" / "raw.csv")
    assert len(source) == 1246 and {r["task"] for r in source} == expected_tasks
    unique(source, "task", "variant")
    assert all(r["repeat"] == "1" for r in source)
    rows = []
    for r in source:
        rows.append({
            "algorithm": ALGORITHMS[r["variant"]],
            "batch": "b2" if r["b"] == "2" else "b3",
            "category": categorical(r["family"]),
            **r,
            "solved": str(r["status"] in DECISIVE),
            "par2Sec": par2(r),
            "peakRssMiB": str(float(r["peakRssKb"]) / 1024) if r["peakRssKb"] else "",
        })
    rows.sort(key=lambda r: (r["task"], r["algorithm"]))
    write_csv("RQ3_E4_623.csv", rows,
              ["algorithm", "batch", "category", *source[0], "solved", "par2Sec", "peakRssMiB"])


def rq4_certified() -> None:
    source = read_csv(RQ4 / "rq4c_paper_data.csv")
    assert len(source) == 41 and len({r["task"] for r in source}) == 23
    unique(source, "task", "algorithm")
    assert all(r["repeat"] == "1" for r in source)
    labels = {
        "certified_unary_depth": ("unary_structure_growth", "一元结构增长"),
        "certified_binary_arity": ("binary_branch_growth", "二元分支增长"),
        "neutral_profile_states": ("constraint_profile", "constraint-profile"),
    }
    rows = []
    for r in source:
        series, series_zh = labels[r["axis"]]
        rows.append({
            "instanceClass": series, "instanceClassZh": series_zh,
            **r,
            "par2Sec": par2(r, float(r["timeoutSec"])),
            "peakRssMiB": str(float(r["peakRssKb"]) / 1024) if r["peakRssKb"] else "",
        })
    assert Counter(r["instanceClass"] for r in rows) == {
        "unary_structure_growth": 24, "binary_branch_growth": 12, "constraint_profile": 5,
    }
    rows.sort(key=lambda r: (r["instanceClass"], int(r["axisValue"]), r["algorithm"]))
    write_csv("RQ4_certified_23.csv", rows,
              ["instanceClass", "instanceClassZh", *source[0], "par2Sec", "peakRssMiB"])


def main() -> None:
    rq1_tiny()
    tasks = rq1_official()
    rq2_full(tasks)
    rq3_e4(tasks)
    rq4_certified()


if __name__ == "__main__":
    main()
