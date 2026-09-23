#!/usr/bin/env python3
"""Split the full paper workload into matched b=2 and b=3 campaigns."""
import argparse
import hashlib
import json
import pathlib


CONSEQUENT = "weakening/weaken_consequent/"


def names(path):
    values = path.read_text().splitlines()
    if not values or len(values) != len(set(values)) or any(not value or value != value.strip() for value in values):
        raise ValueError("Empty, duplicate or malformed task list: " + str(path))
    return set(values)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def split(b2, b3, output):
    paper = names(b2 / "paper_tasks.txt")
    if paper != names(b3 / "paper_tasks.txt"):
        raise ValueError("b=2 and b=3 do not identify the same official paper workload")
    for bound, directory in ((2, b2), (3, b3)):
        supported = names(directory / "matched" / "supported_tasks.txt")
        missing = paper - supported
        if missing:
            raise ValueError(f"b={bound} matched coverage is missing {len(missing)} paper tasks")
    inputs = {}
    for task in sorted(paper):
        left = b2 / "matched_u_free" / task
        right = b3 / "matched_u_free" / task
        if not left.is_file() or not right.is_file() or digest(left) != digest(right):
            raise ValueError("b=2 and b=3 matched inputs differ: " + task)
        inputs[task] = digest(left)
    b3_tasks = sorted(task for task in paper if task.startswith(CONSEQUENT))
    b2_tasks = sorted(paper - set(b3_tasks))
    if not b3_tasks:
        raise ValueError("No Weakening consequent tasks were found")
    output.mkdir(parents=True, exist_ok=False)
    for filename, tasks in (("paper-tasks.txt", sorted(paper)), ("e4-b2-tasks.txt", b2_tasks),
                            ("e4-b3-consequent-tasks.txt", b3_tasks)):
        (output / filename).write_text("".join(task + "\n" for task in tasks))
    manifest = {
        "paperTasks": len(paper), "e4B2Tasks": len(b2_tasks), "e4B3Tasks": len(b3_tasks),
        "b2Preparation": str(b2.resolve()), "b3Preparation": str(b3.resolve()),
        "paperTaskListSha256": digest(output / "paper-tasks.txt"),
        "e4B2TaskListSha256": digest(output / "e4-b2-tasks.txt"),
        "e4B3TaskListSha256": digest(output / "e4-b3-consequent-tasks.txt"),
        "matchedInputSetSha256": hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest(),
    }
    (output / "split-manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--b2", type=pathlib.Path, required=True)
    parser.add_argument("--b3", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()
    split(args.b2.resolve(), args.b3.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
