#!/usr/bin/env python3
"""Recompute the frozen RQ1/E4 counts without launching a solver."""

import collections
import csv
import hashlib
import json
import math
import pathlib
import statistics


ROOT = pathlib.Path(__file__).resolve().parent
METHODS = ("atlas-b", "macro")
DECISIVE = {"SAT", "UNSAT"}


def read_json(path):
    return json.loads(path.read_text())


def read_csv(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def summarize():
    tiny = read_json(ROOT / "rq1-tiny/report.json")
    tiny_rows = read_csv(ROOT / "rq1-tiny/per-run.csv")
    tiny_keys = {(r["caseId"], r["method"]) for r in tiny_rows}
    assert len(tiny_rows) == len(tiny_keys) == tiny["expectedRuns"] == 3000
    assert tiny["expectedCases"] == 1000 and tiny["unresolved"] == tiny["disagreements"] == 0
    tiny_pairs = {}
    for row in tiny_rows:
        tiny_pairs.setdefault(row["caseId"], {})[row["method"]] = row
    assert len(tiny_pairs) == 1000
    tiny_status = collections.Counter()
    for pair in tiny_pairs.values():
        assert set(pair) == {"oracle", "atlas-b", "macro"}
        reference = pair["oracle"]
        assert reference["verification"] == "REFERENCE_EXHAUSTIVE"
        assert reference["status"] in DECISIVE
        tiny_status[reference["status"]] += 1
        for method in METHODS:
            row = pair[method]
            assert (row["status"], row["objectivePrimary"], row["objectiveSecondary"]) == (
                reference["status"], reference["objectivePrimary"], reference["objectiveSecondary"])
            assert row["verification"] == ("PASSED" if row["status"] == "SAT" else "NOT_APPLICABLE_UNSAT")
    assert tiny_status == {"SAT": 819, "UNSAT": 181}

    official = read_json(ROOT / "rq1-official/report.json")
    assert official["totalCases"] == 623 and official["disagreements"] == 0

    all_pairs = {}
    batch_reports = {}
    for batch, expected in (("b2", 584), ("b3", 39)):
        folder = ROOT / ("e4-" + batch)
        raw = folder / "raw.csv"
        rows = read_csv(raw)
        planned = read_json(folder / "expected_runs.json")
        key = lambda r: (r["task"], r["variant"], str(r["repeat"]))
        assert len(planned) == len(rows) == 2 * expected
        assert {key(r) for r in rows} == {key(r) for r in planned}
        assert len({key(r) for r in rows}) == len(rows)
        assert sha256(raw) == official["source"][batch]["rawSha256"]
        assert sha256(folder / "plan.json") == official["source"][batch]["planSha256"]
        assert official["source"][batch]["b"] == int(batch[1:])
        batch_pairs = {}
        for row in rows:
            assert row["variant"] in METHODS and row["repeat"] == "1"
            if row["status"] == "SAT":
                assert row["verification"] == "PASSED"
            batch_pairs.setdefault(row["task"], {})[row["variant"]] = row
        assert len(batch_pairs) == expected
        assert all(set(pair) == set(METHODS) for pair in batch_pairs.values())
        assert not (set(all_pairs) & set(batch_pairs))
        for task, pair in batch_pairs.items():
            all_pairs[task] = (batch, pair)
        batch_reports[batch] = {"cases": expected, "statuses": {
            method: dict(collections.Counter(r["status"] for r in rows if r["variant"] == method))
            for method in METHODS}}

    assert len(all_pairs) == 623
    statuses = {method: collections.Counter() for method in METHODS}
    outcomes = collections.Counter()
    paired_rows = []
    ratios = []
    par2 = {method: [] for method in METHODS}
    batch_outcomes = {batch: collections.Counter() for batch in ("b2", "b3")}
    batch_ratios = {batch: [] for batch in ("b2", "b3")}
    batch_par2 = {batch: {method: [] for method in METHODS} for batch in ("b2", "b3")}
    disagreements = []
    verified_sat_runs = 0
    for task, (batch, pair) in sorted(all_pairs.items()):
        atlas, macro = (pair[method] for method in METHODS)
        assert all(atlas[field] == macro[field] for field in ("B", "b", "p", "objectiveKind"))
        assert int(atlas["b"]) == int(batch[1:])
        solved = {method: pair[method]["status"] in DECISIVE for method in METHODS}
        category = ("both" if all(solved.values()) else "atlas_only" if solved["atlas-b"]
                    else "macro_only" if solved["macro"] else "neither")
        outcomes[category] += 1
        batch_outcomes[batch][category] += 1
        for method in METHODS:
            row = pair[method]
            statuses[method][row["status"]] += 1
            penalty_time = float(row["totalSec"]) if solved[method] else 360.0
            par2[method].append(penalty_time)
            batch_par2[batch][method].append(penalty_time)
            if row["status"] == "SAT":
                verified_sat_runs += 1
        if category == "both":
            left = (atlas["status"], atlas["objectivePrimary"], atlas["objectiveSecondary"])
            right = (macro["status"], macro["objectivePrimary"], macro["objectiveSecondary"])
            if left != right:
                disagreements.append(task)
            ratio = float(atlas["totalSec"]) / float(macro["totalSec"])
            ratios.append(ratio)
            batch_ratios[batch].append(ratio)
        paired_rows.append(dict(batch=batch, task=task, B=atlas["B"], b=atlas["b"],
                                objectiveKind=atlas["objectiveKind"], category=category,
                                atlasBStatus=atlas["status"], macroStatus=macro["status"],
                                atlasBObjectivePrimary=atlas["objectivePrimary"],
                                atlasBObjectiveSecondary=atlas["objectiveSecondary"],
                                macroObjectivePrimary=macro["objectivePrimary"],
                                macroObjectiveSecondary=macro["objectiveSecondary"],
                                atlasBWallSec=atlas["totalSec"], macroWallSec=macro["totalSec"],
                                atlasBVerification=atlas["verification"], macroVerification=macro["verification"]))

    assert not disagreements
    assert outcomes["both"] == official["bothDecisive"] == 331
    assert 623 - outcomes["both"] == official["unresolved"] == 292
    assert verified_sat_runs == official["verifiedSatRuns"] == 727
    assert sum(outcomes.values()) == 623
    for batch in ("b2", "b3"):
        batch_reports[batch]["outcomes"] = dict(batch_outcomes[batch])
        batch_reports[batch]["par2Sec"] = {
            method: statistics.mean(batch_par2[batch][method]) for method in METHODS}
        batch_reports[batch]["commonSolvedSpeedupMedian"] = statistics.median(batch_ratios[batch])
    output = ROOT / "combined"
    output.mkdir(exist_ok=True)
    with (output / "paired.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, paired_rows[0].keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(paired_rows)
    report = {
        "tiny": {"cases": 1000, "runs": 3000, "disagreements": 0,
                 "unresolved": 0, "statusesPerMethod": dict(tiny_status)},
        "official": {"cases": 623, "pairedRuns": 1246, "bothDecisive": outcomes["both"],
                     "unresolved": 623 - outcomes["both"], "disagreements": 0,
                     "verifiedSatRuns": verified_sat_runs, "statuses": {
                         method: dict(statuses[method]) for method in METHODS},
                     "outcomes": dict(outcomes),
                     "par2Sec": {method: statistics.mean(par2[method]) for method in METHODS},
                     "commonSolvedSpeedup": {
                         "definition": "ATLAS-B wall time / MacroATLAS wall time",
                         "count": len(ratios), "median": statistics.median(ratios),
                         "geometricMean": math.exp(statistics.mean(math.log(r) for r in ratios))}},
        "batches": batch_reports,
        "protocol": {"timeoutSec": 180, "par2PenaltySec": 360,
                     "repeatsPerCaseMethod": 1,
                     "unresolvedStatusesAreNotAgreements": True},
    }
    (output / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    summarize()
