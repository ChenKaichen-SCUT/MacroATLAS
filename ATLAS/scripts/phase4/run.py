#!/usr/bin/env python3
"""Serial one-JVM-per-task runner. Formal runs require a clean, tested commit."""
import argparse
import csv
import ctypes
import datetime
import fcntl
import json
import os
import pathlib
import random
import signal
import shutil
import subprocess
import time
from common import ATLAS, FIELDS, digest, environment, java_command, save_json, sha256, task_record


def process_group_rss(group):
    """Sample aggregate live RSS of the JVM and native solver process group (KiB)."""
    total = 0
    for entry in pathlib.Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            # /proc stat comm can contain spaces; fields after the final ')' start at field 3.
            fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
            if int(fields[2]) == group:
                total += int(fields[21]) * os.sysconf("SC_PAGE_SIZE") // 1024
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            pass
    return total


def execute(args, directory, timeout, memory_mb):
    # Linux subreaper: after killing a process group, reap the native solver as well
    # as the JVM/time wrapper, including on hosts whose PID 1 does not reap orphans.
    libc=ctypes.CDLL(None,use_errno=True)
    if libc.prctl(36,1,0,0,0)!=0:  # PR_SET_CHILD_SUBREAPER
        raise OSError(ctypes.get_errno(),"Cannot enable child subreaper")
    with (directory / "stdout.csv").open("w") as out, (directory / "stderr.log").open("w") as err:
        start = time.monotonic()
        proc = subprocess.Popen(["/usr/bin/time", "-v", "-o", str(directory / "resource.txt")] + args,
                                cwd=ATLAS, stdout=out, stderr=err, start_new_session=True)
        peak = 0
        reason = None
        try:
            while proc.poll() is None:
                rss = process_group_rss(proc.pid)
                peak = max(peak, rss)
                if memory_mb and rss > memory_mb * 1024:
                    reason = "RSS_LIMIT"
                elif time.monotonic() - start >= timeout:
                    reason = "TIMEOUT"
                if reason:
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    break
                time.sleep(0.05)
            code = proc.wait()
        finally:
            # Also reap native descendants if the JVM terminated abnormally first.
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()
            while True:
                try:
                    os.waitpid(-proc.pid,0)
                except ChildProcessError:
                    break
    return code, time.monotonic() - start, peak, reason


def row_from_metadata(meta, verification, job, wall, rss):
    aliases = {"B": "nodeBudget", "b": "binaryBudget", "p": "protectedCount", "K": "anchorSlotBudget",
               "qStates": "constraintStateCount", "fiberCount": "fiberCount", "activeAnchors": "activeAnchorCount",
               "activeMacroEdges": "activeMacroEdgeCount", "expandedSize": "expandedNodeCount"}
    row = {k: meta.get(aliases.get(k, k), "") for k in FIELDS}
    row.update(job)
    row.update(totalSec=wall, peakRssKb=rss, verification=verification.get("status", "NOT_RUN"))
    return {k: row.get(k, "") for k in FIELDS}


def check_pair(rows):
    pairs = {}
    for r in rows:
        if r["variant"] not in {"atlas-b", "macro"} or r["status"] not in {"SAT", "UNSAT"}:
            continue
        key = (r["task"], r["repeat"])
        values = (r["status"], str(r["objectivePrimary"]), str(r["objectiveSecondary"]))
        if key in pairs and pairs[key] != values:
            raise RuntimeError("CORRECTNESS FAILURE: matched outcome/objective mismatch for " + str(key))
        pairs[key] = values


def run(a):
    if a.suite != "matched" and (a.B is not None or a.task_budgets):
        raise ValueError("Original/AUTO deployment uses original task bounds; B overrides are matched-only")
    env = environment(a.java)
    if env["dirty"] and not a.pilot:
        raise ValueError("Formal timing requires a clean frozen commit; --pilot labels all results non-publication")
    if not a.pilot:
        gate=json.loads(a.gate.read_text())
        for key in ["commit","solverSha256","alloySha256","applicationSha256","java"]:
            if gate.get(key)!=env[key]:raise ValueError("Correctness certificate does not match current "+key)
        if gate.get("status")!="PASSED":raise ValueError("Correctness gate did not pass")
    root = a.root.resolve()
    names = [n for n in a.tasks.read_text().splitlines() if n]
    if len(names) != len(set(names)):
        raise ValueError("Duplicate task in task list")
    if a.suite == "matched" and a.tasks.name != "supported_tasks.txt":
        raise ValueError("Matched suite must use analyzer-generated supported_tasks.txt")
    if a.suite=="matched" and not a.pilot:
        with a.tasks.with_name("coverage.csv").open() as f:
            supported={r["task"] for r in csv.DictReader(f) if r["supported"]=="true"}
        if set(names)!=supported:
            raise ValueError("Formal matched list differs from complete analyzer support list; preregister a separate preparation root for subsets")
    records = []
    for name in names:
        path = (root / name).resolve()
        path.relative_to(root)
        record=task_record(root,path)
        if a.task_budgets:
            sidecar=json.loads(path.with_suffix(".json").read_text())
            record.update(B=int(sidecar["B"]),b=int(sidecar["b"]))
        records.append(record)
    if a.limit:
        if not a.pilot:
            raise ValueError("Formal subsets require a separate preregistered preparation root; --limit is pilot-only")
        records = records[:a.limit]
    variants = {"original": ["original"], "matched": ["atlas-b", "macro"], "auto": ["original", "auto"]}[a.suite]
    jobs = [dict(r, variant=v, repeat=i) for i in range(1, a.repeats + 1) for r in records for v in variants]
    random.Random(a.seed).shuffle(jobs)
    config = dict(suite=a.suite, benchmarkRoot=str(root), taskListHash=digest(records), timeoutSec=a.timeout, heap=a.heap,
                  memoryLimitMb=a.memory_mb, memoryLimitMethod="sampled aggregate RSS guard" if a.memory_mb else "none",
                  cpuAffinity=a.cpu, repeats=a.repeats, seed=a.seed, pilot=a.pilot, java=a.java,
                  binaryBudget=a.b, nodeBudget=a.B, perTaskBudgets=a.task_budgets,
                  keepSolverTemp=a.keep_solver_temp, commandTemplate=java_command(a.java, a.heap))
    result = a.output.resolve() if a.output else ATLAS / "results" / env["commit"] / env["machine"] / datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    if result.exists():
        raise ValueError("Output must be new; partial runs retain their logs and can be selected for a new rerun")
    result.mkdir(parents=True)
    save_json(result / "manifest.json", dict(env, **config))
    save_json(result / "expected_runs.json", jobs)
    rows = []
    # A repository-wide advisory lock prevents accidental competing benchmark controllers.
    with (ATLAS / "results/.runner.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        for index, job in enumerate(jobs):
            folder = result / ("%05d-%s-%s-r%d" % (index, digest(job)[:12], job["variant"], job["repeat"]))
            folder.mkdir()
            path = root / job["task"]
            if sha256(path) != job["sha256"]:
                raise RuntimeError("Input changed after manifest creation")
            cmd = java_command(a.java, a.heap) + ["--mode", job["variant"], "--file", str(path), "--b", str(job.get("b",a.b)), "--output", str(folder)]
            temporary = folder / "solver-tmp"
            temporary.mkdir()
            cmd.insert(1, "-Djava.io.tmpdir=" + str(temporary))
            bound=job.get("B",a.B)
            if bound is not None:
                cmd += ["--B", str(bound)]
            if a.cpu:
                cmd = ["taskset", "-c", a.cpu] + cmd
            save_json(folder / "command.json", dict(job, command=cmd, commit=env["commit"]))
            code, wall, rss, reason = execute(cmd, folder, a.timeout, a.memory_mb)
            if not a.keep_solver_temp:
                shutil.rmtree(temporary)
            meta = json.loads((folder / "metadata.json").read_text()) if (folder / "metadata.json").exists() else {"status": "ERROR", "solverMode": "NONE"}
            ver = json.loads((folder / "verification.json").read_text()) if (folder / "verification.json").exists() else {"status": "NOT_RUN"}
            if reason:
                meta.update(status="TIMEOUT" if reason == "TIMEOUT" else "ERROR", error=reason)
            elif code != 0 and meta["status"] not in {"ERROR", "VERIFICATION_FAILED"}:
                meta.update(status="ERROR", error="PROCESS_EXIT_%d" % code)
            if "OutOfMemoryError" in (folder / "stderr.log").read_text():
                meta.update(status="ERROR", error="JVM_OOM")
            if meta.get("solverMode") in {"MACRO", "ATLAS_B"} and meta["status"] == "SAT" and ver["status"] != "PASSED":
                meta["status"] = "VERIFICATION_FAILED"
            save_json(folder / "metadata.json", meta)
            for name in ["verification.json", "timing.json", "analysis.json"]:
                if not (folder / name).exists():
                    save_json(folder / name, ver if name == "verification.json" else {})
            row = row_from_metadata(meta, ver, job, wall, rss)
            save_json(folder / "result.json", row)
            rows.append(row)
            with (result / "raw.csv").open("w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n");writer.writeheader();writer.writerows(rows)
            print("%d/%d %s %s %s %.2fs %.1fMiB" % (index + 1, len(jobs), job["variant"], job["task"], row["status"], wall, rss / 1024), flush=True)
            if row["status"] == "VERIFICATION_FAILED":
                raise RuntimeError("Correctness gate failed; stopping experiment")
            check_pair(rows)
    print(result)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=pathlib.Path, required=True)
    p.add_argument("--tasks", type=pathlib.Path, required=True)
    p.add_argument("--suite", choices=["original", "matched", "auto"], required=True)
    p.add_argument("--output", type=pathlib.Path)
    p.add_argument("--repeats", type=int, default=1)
    p.add_argument("--seed", type=int, default=20260922)
    p.add_argument("--timeout", type=float, default=180)
    p.add_argument("--b", type=int, default=2)
    p.add_argument("--B", type=int)
    p.add_argument("--task-budgets", action="store_true", help="Use B,b from generated synthetic JSON sidecars for both variants")
    p.add_argument("--java", default="java")
    p.add_argument("--heap", default="4g")
    p.add_argument("--memory-mb", type=int, default=0)
    p.add_argument("--cpu", help="Identical taskset CPU list for both variants")
    p.add_argument("--limit", type=int)
    p.add_argument("--pilot", action="store_true")
    p.add_argument("--keep-solver-temp", action="store_true", help="Retain per-task native solver scratch files; models and logs are always retained")
    p.add_argument("--gate", type=pathlib.Path, default=ATLAS/"generated/phase4-gate.json")
    a = p.parse_args()
    if a.repeats < 1 or a.timeout <= 0 or a.b < 0 or a.memory_mb < 0 or (a.B is not None and a.B < 1) or (a.limit is not None and a.limit < 1):
        p.error("Invalid repeat/timeout/budget")
    (ATLAS / "results").mkdir(exist_ok=True)
    run(a)


if __name__ == "__main__":
    main()
