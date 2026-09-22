#!/usr/bin/env python3
"""Reject incomplete runs, failed verifiers, mixed environments and unfair matched pairs."""
import argparse
import csv
import json
import pathlib
from common import STATUSES
from run import check_pair


def validate(directory, allow_partial=False):
    manifest = json.loads((directory / "manifest.json").read_text())
    jobs = json.loads((directory / "expected_runs.json").read_text())
    with (directory / "raw.csv").open() as f:
        rows = list(csv.DictReader(f))
    key = lambda r: (r["task"], r["variant"], int(r["repeat"]))
    expected = {key(r) for r in jobs}
    expected_records = {key(r): r for r in jobs}
    assert len(expected) == len(jobs), "Duplicate expected jobs"
    actual = [key(r) for r in rows]
    assert len(actual) == len(set(actual)), "Duplicate runs"
    assert set(actual) <= expected, "Unexpected run"
    if not allow_partial:
        assert set(actual) == expected, "Missing expected runs"
    artifacts = {}
    for path in directory.glob("*/command.json"):
        command = json.loads(path.read_text())
        assert command["commit"] == manifest["commit"], "Mixed commits"
        assert key(command) in expected_records and all(command[k] == v for k, v in expected_records[key(command)].items()), "Changed command/input record"
        artifacts[key(command)] = path.parent
    for row in rows:
        assert row["status"] in STATUSES, row
        assert key(row) in artifacts, "Missing raw artifacts"
        folder = artifacts[key(row)]
        for name in ["metadata.json", "analysis.json", "timing.json", "verification.json", "result.json", "stdout.csv", "stderr.log"]:
            assert (folder / name).is_file(), "Missing " + name
        recorded = json.loads((folder / "result.json").read_text())
        assert all(str(recorded[k]) == v for k, v in row.items()), "CSV disagrees with per-task result"
        assert row["status"] != "VERIFICATION_FAILED", "Correctness failure"
        if row["solverMode"] in {"MACRO", "ATLAS_B"} and row["status"] == "SAT":
            assert row["verification"] == "PASSED", "Unverified solution"
        if row["status"] == "FALLBACK":
            assert row["variant"] == "auto" and row["solverMode"] == "ORIGINAL" and row["fallbackReason"]
            assert row["outcome"] in {"SAT", "UNSAT"}
        if row["solverMode"] == "ORIGINAL" and (row["status"] == "SAT" or (row["status"] == "FALLBACK" and row["outcome"] == "SAT")):
            assert row["verification"] == "TRACE_PASSED", "Unverified original solution"
        if row["variant"] == "original":
            assert row["solverMode"] in {"ORIGINAL", "NONE"} and not row["fiberCount"], "OFF entered macro path"
        if row["variant"] == "macro":
            assert row["status"] != "FALLBACK", "Unexpected FORCE fallback"
    check_pair(rows)
    pairs = {}
    for row in rows:
        if row["variant"] in {"atlas-b", "macro"} and row["status"] in {"SAT", "UNSAT"}:
            k = (row["task"], row["repeat"])
            domain = tuple(row[x] for x in ["B", "b", "p", "objectiveKind"])
            if k in pairs:
                assert pairs[k] == domain, "Different matched domains/objectives"
            pairs[k] = domain
    return rows, manifest


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("directory", type=pathlib.Path)
    p.add_argument("--allow-partial", action="store_true")
    a = p.parse_args()
    rows, _ = validate(a.directory, a.allow_partial)
    print("VALID:", len(rows), "runs; no verification failures or matched objective mismatches")
