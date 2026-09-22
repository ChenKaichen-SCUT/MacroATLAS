#!/usr/bin/env python3
"""Inventory every artifact input; make U-free copies without silently editing originals."""
import argparse
import collections
import csv
import json
import pathlib
import re
import subprocess
from common import ATLAS, digest, environment, java_command, save_json, task_record


def atlas_format(text):
    parts = text.split("---")
    if len(parts) < 4:
        return False
    ops = {s.strip() for s in parts[2].strip().split(",")}
    return ops <= {"!", "X", "F", "G", "U", "&", "|", "->", "prop"} and bool(re.fullmatch(r"\d+|\[\d+\]", parts[3].strip()))


def prepare(root, output, b, java):
    if output.exists():
        raise ValueError("Use a new preparation directory; existing generated inputs are not overwritten")
    output.mkdir(parents=True)
    original, matched, other = [], [], []
    for file in sorted(root.rglob("*.trace")):
        record = task_record(root, file)
        text = file.read_text()
        if not atlas_format(text):
            record["format"] = "OTHER_TOOL_INPUT"
            other.append(record)
            continue
        record["format"] = "ATLAS"
        original.append(record)
        parts = text.split("---")
        old_ops = [s.strip() for s in parts[2].strip().split(",")]
        new_ops = [op for op in old_ops if op != "U"]
        parts[2] = "\n" + ",".join(new_ops) + "\n"
        destination = output / "matched_u_free" / record["task"]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text("---".join(parts))
        if file.with_suffix(".json").exists():
            destination.with_suffix(".json").write_bytes(file.with_suffix(".json").read_bytes())
        matched.append(dict(task_record(output / "matched_u_free", destination), originalSha256=record["sha256"],
                            removedU="U" in old_ops, originalOperators=old_ops, matchedOperators=new_ops))
    save_json(output / "inventory.json", {"root": str(root), "original": original, "matched": matched, "otherFormats": other,
                                          "taskListHash": digest(original), "environment": environment(java)})
    # Identify the paper's actual workload from its archived result tables, never from a hardcoded count.
    if root == (ATLAS / "benchmark").resolve():
        tables=["baselines/baseline_alloy_all.csv","peterson/peterson_alloy.csv","voting/voting_alloy.csv",
                "robot/robot_alloy.csv","weakening/weakening_alloy_gr1_new.csv"]
        names={r["task"] for r in original};paper=[];provenance=[]
        for table in tables:
            with (ATLAS/"benchmark_results"/table).open() as f:
                for row in csv.DictReader(f):
                    old=row["filename"].replace("\\","/")
                    candidates=[n for n in names if old.endswith(n)]
                    if not candidates:
                        candidates=[n for n in names if pathlib.PurePosixPath(n).name==pathlib.PurePosixPath(old).name]
                    if len(candidates)!=1:
                        raise ValueError("Ambiguous/missing archived paper input: "+old)
                    name=candidates[0];paper.append(name);provenance.append(dict(task=name,table=table,archivedFilename=old))
        if len(paper)!=len(set(paper)):
            raise ValueError("Duplicate paper workload row")
        (output/"paper_tasks.txt").write_text("".join(n+"\n" for n in sorted(paper)))
        save_json(output/"paper-provenance.json",provenance)
    for kind, records in [("original_tasks.txt", original), ("other_tool_inputs.txt", other)]:
        (output / kind).write_text("".join(r["task"] + "\n" for r in records))
    # The frozen Kotlin analyzer is the authority for both official coverage and matched support.
    for name, directory in [("official", root), ("matched", output / "matched_u_free")]:
        subprocess.run(java_command(java) + ["--mode", "coverage", "--root", str(directory), "--b", str(b),
                                             "--output", str(output / name)], cwd=ATLAS, check=True)
        counts = collections.defaultdict(collections.Counter)
        with (output / name / "coverage.csv").open() as f:
            for row in csv.DictReader(f):
                counts[row["family"]]["total"] += 1
                counts[row["family"]]["supported"] += row["supported"] == "true"
                counts[row["family"]][row["reason"]] += 1
        save_json(output / name / "coverage-summary.json", counts)
    return original


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=pathlib.Path, default=ATLAS / "benchmark")
    p.add_argument("--output", type=pathlib.Path, required=True)
    p.add_argument("--b", type=int, default=2)
    p.add_argument("--java", default="java")
    a = p.parse_args()
    prepare(a.root.resolve(), a.output.resolve(), a.b, a.java)


if __name__ == "__main__":
    main()
