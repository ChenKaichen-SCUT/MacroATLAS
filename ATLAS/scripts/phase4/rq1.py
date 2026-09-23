#!/usr/bin/env python3
"""RQ1 tiny exhaustive experiment: immutable inputs, one attempt per method/case."""
import argparse
import collections
import concurrent.futures
import csv
import datetime
import hashlib
import json
import os
import pathlib
import random
import re
import shutil
import signal
import subprocess
import tarfile
import threading
import time

from common import ATLAS, digest, environment, save_csv, save_json, sha256
from isolation import allocate, topology

MODES = ("oracle", "atlas-b", "macro")
JAVA_CLASS = "cmu.s3d.ltl.macro.search.Rq1TinyMain"
JAVA = "/srv/macroatlas/jdks/jdk8u462-b08/bin/java"
PYTHON = "/srv/macroatlas/venv/bin/python"
SERVICE = "macroatlas-rq1"
PRINT_LOCK = threading.Lock()


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def read(path):
    return json.loads(pathlib.Path(path).read_text())


def case_input(index, seed):
    """Generate diverse, outcome-independent tiny domains with known target patterns.

    The oracle still decides the true optimum; the patterns only shape the input.
    """
    rng = random.Random(seed + index * 1000003)
    families = ("plain", "nnf", "cnf", "dnf", "required", "no_dag_reuse", "global_prop", "repair")
    family = families[index % len(families)]
    cycle = index // len(families)
    pattern = cycle % (3 if family == "repair" else 5 if family in {"cnf", "dnf", "global_prop"} else 8)
    constraints = {
        "plain": "",
        "nnf": "fact { all n: Neg | n.l in Literal }",
        "cnf": "fact { all n: DAGNode | n in (Literal + Neg + And + Or) all n: Neg | n.l in Literal all n: Or | no childrenOf[n] & And }",
        "dnf": "fact { all n: DAGNode | n in (Literal + Neg + And + Or) all n: Neg | n.l in Literal all n: And | no childrenOf[n] & Or }",
        "required": "fact { x0 in childrenAndSelfOf[root] }",
        "no_dag_reuse": "fact { all n: DAGNode | lone n.~(l+r) }",
        "global_prop": "fact { root in G all n: childrenAndSelfOf[root.l] | n in (Literal + Neg + And + Or + Imply) }",
        "repair": "one sig F0 extends F {}\nfact { root = F0 }\nfact { x0 in childrenAndSelfOf[root] }\nfact { maxsome[2] subDAG[root] & (F0->x0) }",
    }[family]
    ap = 2 if pattern in {3, 4} and family != "repair" else 1
    kind = ("conflict", "literal", "negated", "and", "or", "eventually", "next", "next_next")[pattern]
    if family == "repair":
        kind = ("conflict", "repair_kept", "repair_dropped")[pattern]
    elif family == "global_prop":
        kind = ("conflict", "global_literal", "global_negated", "global_and", "global_or")[pattern]
    elif family in {"cnf", "dnf"}:
        kind = ("conflict", "literal", "negated", "and", "or")[pattern]
    B = {"conflict": 2, "literal": 2, "negated": 3, "and": 3, "or": 3,
         "eventually": 3, "next": 3, "next_next": 4,
         "repair_kept": 3, "repair_dropped": 4,
         "global_literal": 3, "global_negated": 4, "global_and": 4, "global_or": 4}[kind]
    B = max(B, ap)
    b = 1 if kind in {"and", "or", "global_and", "global_or"} else 0

    def constant(bits):
        n = 1 + rng.randrange(8)
        states = [list(bits) for _ in range(n)]
        return states, rng.randrange(n)

    def temporal(bits, zero_tail=False):
        tail = [0 if zero_tail else rng.randrange(2) for _ in range(rng.randrange(6))]
        states = [[int(value)] for value in list(bits) + tail]
        return states, rng.randrange(len(states))

    if kind == "conflict":
        positive = [constant([1]), constant([rng.randrange(2)])]
        negative = [positive[0]]
    elif kind in {"literal", "repair_kept", "global_literal"}:
        positive = [constant([1])]
        negative = [constant([0])]
    elif kind in {"negated", "repair_dropped", "global_negated"}:
        positive = [constant([0])]
        negative = [constant([1])]
    elif kind in {"and", "global_and"}:
        positive = [constant([1, 1])]
        negative = [constant([1, 0]), constant([0, 1])]
    elif kind in {"or", "global_or"}:
        positive = [constant([1, 0]), constant([0, 1])]
        negative = [constant([0, 0])]
    elif kind == "eventually":
        positive = [temporal([0, 1, 0])]
        negative = [temporal([0, 0, 0], zero_tail=True)]
    elif kind == "next":
        positive = [temporal([0, 1, 0])]
        negative = [temporal([0, 0, 1])]
    else:
        positive = [temporal([0, 0, 1, 0])]
        negative = [temporal([0, 0, 0, 1])]

    def render(trace):
        states, loop = trace
        return ";".join(",".join(str(bit) for bit in state) for state in states) + "::" + str(loop)

    pos = [render(trace) for trace in positive]
    neg = [render(trace) for trace in negative]
    text = "\n".join(pos) + "\n---\n" + "\n".join(neg) + "\n---\n!,X,F,G,&,|,->\n---\n[" + str(B - ap) + "]\n---\n\n---\n" + constraints + "\n"
    record = dict(id=f"tiny_{index:05d}", family=family, index=index, caseSeed=seed + index * 1000003,
                  inputPattern=kind, B=B, b=b, numAP=ap, positiveTraceCount=len(pos),
                  negativeTraceCount=len(neg), conflictByConstruction=kind == "conflict", constraints=constraints)
    return text, record


def prepare(args):
    output = args.output.resolve()
    if output.exists():
        raise ValueError("Dataset directory must be new")
    if args.count < 1 or args.offset < 0:
        raise ValueError("Invalid count/offset")
    output.mkdir(parents=True)
    records = []
    seen_inputs = set()
    for index in range(args.offset, args.offset + args.count):
        for salt in range(10000):
            content, record = case_input(index, args.seed + salt * 10000019)
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            if content_hash not in seen_inputs:
                break
        else:
            raise RuntimeError("Unable to generate a unique input for case " + str(index))
        seen_inputs.add(content_hash)
        record["collisionSalt"] = salt
        path = output / "inputs" / record["family"] / (record["id"] + ".trace")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        record["task"] = path.relative_to(output / "inputs").as_posix()
        record["inputSha256"] = sha256(path)
        assert record["inputSha256"] == content_hash
        records.append(record)
    manifest = dict(schemaVersion=1, seed=args.seed, offset=args.offset, count=args.count,
                    generatorSha256=sha256(pathlib.Path(__file__)), cases=records)
    save_json(output / "dataset.json", manifest)
    print(f"Prepared {len(records)} RQ1 cases at {output}; no solver was run")
    print("Families:", dict(collections.Counter(r["family"] for r in records)))


def classes_hash():
    root = ATLAS / "target/test-classes"
    return digest([(p.relative_to(root).as_posix(), sha256(p)) for p in sorted(root.rglob("*")) if p.is_file()])


def test_classpath():
    file = ATLAS / "target/rq1-test-classpath.txt"
    if not file.is_file():
        raise ValueError("Build the test classpath with Maven before planning")
    return os.pathsep.join((str(ATLAS / "target/test-classes"), str(ATLAS / "target/classes"),
                            str(ATLAS / "lib/AlloyMax-1.0.3.jar"), file.read_text().strip()))


def plan(args):
    output = args.output.resolve()
    dataset = args.dataset.resolve()
    if output.exists():
        raise ValueError("Experiment directory must be new")
    data = read(dataset / "dataset.json")
    if args.workers < 1 or args.timeout <= 0:
        raise ValueError("Invalid workers/timeout")
    env = environment(args.java)
    if env["dirty"]:
        raise ValueError("Commit source and specifications before a formal RQ1 plan")
    gate = read(args.gate)
    if gate.get("status") != "PASSED" or any(gate.get(k) != env[k] for k in
        ("commit", "java", "applicationSha256", "solverSha256", "alloySha256")):
        raise ValueError("Correctness gate is missing or does not match this build")
    if not (ATLAS / "target/test-classes" / "cmu/s3d/ltl/macro/search/Rq1TinyMain.class").is_file():
        raise ValueError("RQ1 Java entry point was not compiled")
    cpus, reserved = allocate(topology(), args.workers)
    output.mkdir(parents=True)
    inputs = output / "inputs"
    shutil.copytree(dataset / "inputs", inputs)
    cases = []
    for entry in data["cases"]:
        path = inputs / entry["task"]
        if sha256(path) != entry["inputSha256"]:
            raise ValueError("Dataset input changed: " + entry["task"])
        cases.append(entry)
    p = dict(schemaVersion=1, createdUtc=utc(), sourceCommit=env["commit"], sourceEnvironment=env,
             datasetManifestSha256=sha256(dataset / "dataset.json"), datasetCount=len(cases), cases=cases,
             methods=list(MODES), attemptsPerMethodCase=1, timeoutSec=args.timeout, workers=args.workers,
             workerCpus=cpus, reservedCpus=reserved, java=str(pathlib.Path(args.java).resolve()),
             javaHeap=args.heap, testClassesSha256=classes_hash(), testClasspathSha256=sha256(ATLAS / "target/rq1-test-classpath.txt"),
             gateSha256=sha256(args.gate), noAutomaticRerunAfterInterruptedAttempt=True)
    save_json(output / "plan.json", p)
    (output / "plan.sha256").write_text(sha256(output / "plan.json") + "  plan.json\n")
    shutil.copy2(dataset / "dataset.json", output / "dataset.json")
    shutil.copy2(args.gate, output / "correctness-gate.json")
    save_json(output / "state.json", dict(status="READY", updatedUtc=utc()))
    (output / "logs").mkdir()
    (output / "logs/controller.log").touch()
    with tarfile.open(output / "inputs.tar.gz", "w:gz", compresslevel=1) as archive:
        archive.add(inputs, arcname="inputs")
    subprocess.run(["git", "bundle", "create", str(output / "source.bundle"), "HEAD", "macroatlas-phase3-frozen"], cwd=ATLAS, check=True)
    save_json(output / "checksums.json", {name: sha256(output / name) for name in
        ("plan.json", "dataset.json", "correctness-gate.json", "inputs.tar.gz", "source.bundle")})
    print(f"Planned {len(cases)} cases x {len(MODES)} methods = {len(cases) * len(MODES)} one-attempt jobs")
    print("Worker CPUs:", cpus, "reserved:", reserved)
    print(output)


def load_plan(directory):
    directory = directory.resolve()
    if sha256(directory / "plan.json") != (directory / "plan.sha256").read_text().split()[0]:
        raise ValueError("Plan checksum changed")
    p = read(directory / "plan.json")
    if p["methods"] != list(MODES) or p["attemptsPerMethodCase"] != 1:
        raise ValueError("Method/attempt protocol changed")
    if len(p["cases"]) != len({c["id"] for c in p["cases"]}):
        raise ValueError("Duplicate case IDs")
    if sha256(directory / "dataset.json") != p["datasetManifestSha256"]:
        raise ValueError("Dataset manifest changed")
    if classes_hash() != p["testClassesSha256"] or sha256(ATLAS / "target/rq1-test-classpath.txt") != p["testClasspathSha256"]:
        raise ValueError("Compiled RQ1 code/classpath changed")
    env = environment(p["java"])
    if env["dirty"] or env["commit"] != p["sourceCommit"] or env["applicationSha256"] != p["sourceEnvironment"]["applicationSha256"]:
        raise ValueError("Source/build changed after planning")
    return p


def record_path(directory, case, mode):
    return directory / "jobs" / case["id"] / mode / "record.json"


def save_record(directory, case, mode, info):
    result = dict(caseId=case["id"], task=case["task"], family=case["family"], method=mode,
                  inputSha256=case["inputSha256"], attempt=1, **info)
    save_json(record_path(directory, case, mode), result)
    return result


def run_job(directory, plan_data, case, mode, cpu, cp):
    folder = record_path(directory, case, mode).parent
    final = folder / "record.json"
    if final.exists():
        saved = read(final)
        if saved["inputSha256"] != case["inputSha256"] or saved["method"] != mode or saved["attempt"] != 1:
            raise ValueError("Completed result identity changed")
        return saved
    if folder.exists():
        # A crashed or interrupted JVM must not be launched a second time.
        raw = folder / "result.json"
        if raw.is_file():
            data = read(raw)
            return save_record(directory, case, mode, dict(status=data["status"], verification=data.get("verification", "NOT_RUN"),
                totalSec=data.get("totalSec", 0), peakRssKb="", objectiveKind=data.get("objectiveKind", ""),
                objectivePrimary=data.get("objectivePrimary", ""), objectiveSecondary=data.get("objectiveSecondary", ""),
                recoveredFromCompletedJvm=True, metrics=data))
        return save_record(directory, case, mode, dict(status="INTERRUPTED_UNRECORDED", verification="NOT_RUN",
            totalSec="", objectiveKind="", objectivePrimary="", objectiveSecondary="",
            error="JVM was started but no final result exists; no automatic second attempt"))
    folder.mkdir(parents=True)
    path = directory / "inputs" / case["task"]
    if sha256(path) != case["inputSha256"]:
        raise ValueError("Input changed after planning")
    command = ["taskset", "-c", cpu, plan_data["java"], "-XX:ActiveProcessorCount=2", "-Xms256m",
               "-Xmx" + plan_data["javaHeap"], "-Djava.library.path=" + str(ATLAS / "lib"),
               "-cp", cp, JAVA_CLASS, "--mode", mode, "--file", str(path), "--B", str(case["B"]),
               "--b", str(case["b"]), "--output", str(folder)]
    save_json(folder / "started.json", dict(command=command, startedUtc=utc(), sourceCommit=plan_data["sourceCommit"],
                                            inputSha256=case["inputSha256"], attempt=1))
    started = time.monotonic()
    with (folder / "stdout.log").open("w") as stdout, (folder / "stderr.log").open("w") as stderr:
        process = subprocess.Popen(["/usr/bin/time", "-v", "-o", str(folder / "resource.txt")] + command,
                                   cwd=ATLAS, stdout=stdout, stderr=stderr, start_new_session=True)
        try:
            code = process.wait(timeout=plan_data["timeoutSec"])
            timed_out = False
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGKILL)
            code = process.wait()
    wall = time.monotonic() - started
    raw = folder / "result.json"
    data = read(raw) if raw.is_file() else {}
    status = "TIMEOUT" if timed_out else data.get("status", "ERROR")
    if code != 0 and not timed_out and status not in {"ERROR", "VERIFICATION_FAILED"}:
        status = "ERROR"
    resource = folder / "resource.txt"
    peak_rss = ""
    if resource.is_file():
        for line in resource.read_text(errors="replace").splitlines():
            if "Maximum resident set size (kbytes):" in line:
                peak_rss = int(line.rsplit(":", 1)[1].strip())
    info = dict(status=status, verification=data.get("verification", "NOT_RUN"), totalSec=wall, peakRssKb=peak_rss,
                objectiveKind=data.get("objectiveKind", ""), objectivePrimary=data.get("objectivePrimary", ""),
                objectiveSecondary=data.get("objectiveSecondary", ""), processExitCode=code,
                error=data.get("error", ""), metrics=data)
    result = save_record(directory, case, mode, info)
    with PRINT_LOCK:
        print(utc(), case["id"], mode, status, f"{wall:.2f}s", flush=True)
    return result


def status(directory, quiet=False):
    p = read(directory / "plan.json")
    counts = collections.Counter()
    statuses = collections.defaultdict(collections.Counter)
    cases_complete = 0
    for case in p["cases"]:
        present = 0
        for mode in MODES:
            path = record_path(directory, case, mode)
            if path.is_file():
                value = read(path)
                statuses[mode][value["status"]] += 1
                if value["status"] != "INTERRUPTED_UNRECORDED":
                    counts[mode] += 1
                    present += 1
        if present == len(MODES):
            cases_complete += 1
    n = len(p["cases"])
    state = read(directory / "state.json")["status"]
    official = directory.parent / "rq1-official" / "report.json"
    if not quiet:
        print(f"RQ1 tiny cases {cases_complete}/{n} | oracle {counts['oracle']}/{n} | ATLAS-B {counts['atlas-b']}/{n} | MacroATLAS {counts['macro']}/{n} | state={state}")
        for mode in MODES:
            print(mode, dict(statuses[mode]))
        print("RQ1 official E4:", "IMPORTED" if official.is_file() else "PENDING transfer of completed E4 results")
    return counts, cases_complete


def run(args):
    directory = args.directory.resolve()
    p = load_plan(directory)
    for case in p["cases"]:
        if sha256(directory / "inputs" / case["task"]) != case["inputSha256"]:
            raise ValueError("Frozen input differs: " + case["task"])
    cp = test_classpath()
    save_json(directory / "state.json", dict(status="RUNNING", updatedUtc=utc()))
    stop = threading.Event()
    def worker(index):
        for position, case in enumerate(p["cases"]):
            if position % p["workers"] != index or stop.is_set():
                continue
            for mode in MODES:
                record = run_job(directory, p, case, mode, p["workerCpus"][index], cp)
                if record["status"] in {"VERIFICATION_FAILED", "INTERRUPTED_UNRECORDED"}:
                    stop.set()
                    return
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=p["workers"]) as executor:
            futures = [executor.submit(worker, i) for i in range(p["workers"])]
            for future in concurrent.futures.as_completed(futures):
                future.result()
        counts, complete = status(directory, quiet=True)
        state = "COMPLETE" if complete == len(p["cases"]) else "FAILED"
        save_json(directory / "state.json", dict(status=state, updatedUtc=utc(), completeCases=complete))
        status(directory)
        if state != "COMPLETE":
            raise RuntimeError("RQ1 incomplete; no interrupted attempt will be repeated automatically")
    except BaseException as exc:
        save_json(directory / "state.json", dict(status="FAILED", updatedUtc=utc(), error=str(exc)))
        raise


def summarize(args):
    directory = args.directory.resolve()
    p = load_plan(directory)
    details = []
    disagreements = []
    unresolved = []
    for case in p["cases"]:
        pair = {}
        for mode in MODES:
            path = record_path(directory, case, mode)
            if not path.is_file():
                unresolved.append(dict(caseId=case["id"], method=mode, reason="MISSING"))
                continue
            row = read(path)
            if row["inputSha256"] != case["inputSha256"] or row["attempt"] != 1:
                raise ValueError("Result identity/attempt mismatch")
            pair[mode] = row
            metrics = row.get("metrics", {})
            details.append(dict(caseId=case["id"], family=case["family"], method=mode,
                status=row["status"], objectiveKind=row.get("objectiveKind", ""),
                objectivePrimary=row.get("objectivePrimary", ""), objectiveSecondary=row.get("objectiveSecondary", ""),
                verification=row.get("verification", ""), totalSec=row.get("totalSec", ""),
                B=case["B"], b=case["b"], numAP=case["numAP"],
                positiveTraceCount=case["positiveTraceCount"], negativeTraceCount=case["negativeTraceCount"],
                finalFormulaSize=metrics.get("finalFormulaSize", ""), binaryNodeCount=metrics.get("binaryNodeCount", ""),
                unaryNodeCount=metrics.get("unaryNodeCount", ""), unaryDepth=metrics.get("unaryDepth", ""),
                dagNodeCount=metrics.get("dagNodeCount", ""), hasSharing=metrics.get("hasSharing", ""),
                positiveTracePassed=metrics.get("positiveTracePassed", ""),
                negativeTracePassed=metrics.get("negativeTracePassed", ""),
                constraintAutomatonPassed=metrics.get("constraintAutomatonPassed", ""),
                identityConstraintsPassed=metrics.get("identityConstraintsPassed", ""),
                vars=metrics.get("vars", ""), backendTotalClauses=metrics.get("backendTotalClauses", ""),
                peakRssKb=row.get("peakRssKb", ""), error=row.get("error", "")))
        if len(pair) < len(MODES):
            continue
        oracle = pair["oracle"]
        if oracle["status"] not in {"SAT", "UNSAT"}:
            unresolved.append(dict(caseId=case["id"], method="oracle", reason=oracle["status"]))
            continue
        for mode in ("atlas-b", "macro"):
            row = pair[mode]
            if row["status"] not in {"SAT", "UNSAT"}:
                unresolved.append(dict(caseId=case["id"], method=mode, reason=row["status"]))
                continue
            if row["status"] != oracle["status"]:
                disagreements.append(dict(caseId=case["id"], method=mode, kind="STATUS",
                                          expected=oracle["status"], actual=row["status"]))
            elif row["status"] == "SAT" and (str(row["objectivePrimary"]), str(row["objectiveSecondary"])) != (
                    str(oracle["objectivePrimary"]), str(oracle["objectiveSecondary"])):
                disagreements.append(dict(caseId=case["id"], method=mode, kind="OBJECTIVE",
                    expected=[oracle["objectivePrimary"], oracle["objectiveSecondary"]],
                    actual=[row["objectivePrimary"], row["objectiveSecondary"]]))
            if row["status"] == "SAT" and row["verification"] != "PASSED":
                disagreements.append(dict(caseId=case["id"], method=mode, kind="VERIFICATION",
                    expected="PASSED", actual=row["verification"]))
    output = directory / "summary"
    output.mkdir(exist_ok=True)
    if details:
        save_csv(output / "per-run.csv", details, list(details[0]))
    save_json(output / "disagreements.json", disagreements)
    save_json(output / "unresolved.json", unresolved)
    report = dict(expectedCases=len(p["cases"]), expectedRuns=len(p["cases"]) * len(MODES),
                  recordedRuns=len(details), disagreements=len(disagreements), unresolved=len(unresolved),
                  families=dict(collections.Counter(c["family"] for c in p["cases"])),
                  note="TIMEOUT/ERROR/missing runs are unresolved, never counted as agreement")
    save_json(output / "report.json", report)
    print(json.dumps(report, indent=2))



def official(args):
    from validate_results import validate
    destinations = (("b2", args.b2.resolve(), 584), ("b3", args.b3.resolve(), 39))
    if args.output.exists():
        raise ValueError("Official RQ1 output must be new")
    all_pairs = {}
    source = {}
    for name, directory, expected in destinations:
        if read(directory / "state.json")["status"] != "COMPLETE":
            raise ValueError(name + " E4 campaign is incomplete")
        plan_data = read(directory / "plan.json")
        phases = plan_data["phases"]
        if len(phases) != 1 or phases[0]["id"] != "e4-matched" or phases[0]["variants"] != ["atlas-b", "macro"] or phases[0]["repeats"] != 1:
            raise ValueError("Unexpected E4 protocol in " + name)
        if len(phases[0]["tasks"]) != expected:
            raise ValueError("Wrong E4 task count in " + name)
        rows, manifest = validate(directory / "e4-matched" / "merged")
        if len(rows) != 2 * expected:
            raise ValueError("Incomplete E4 result set in " + name)
        source[name] = dict(campaign=str(directory), commit=plan_data["environment"]["commit"],
                            planSha256=sha256(directory / "plan.json"), rawSha256=sha256(directory / "e4-matched" / "merged" / "raw.csv"),
                            cases=expected, b=plan_data["b"])
        for row in rows:
            key = row["task"]
            if key not in all_pairs:
                all_pairs[key] = {}
            if row["variant"] in all_pairs[key]:
                raise ValueError("Duplicate official task/method: " + key)
            all_pairs[key][row["variant"]] = row
    if len(all_pairs) != 623 or any(set(pair) != {"atlas-b", "macro"} for pair in all_pairs.values()):
        raise ValueError("Official E4 must contain exactly 623 paired tasks")
    per_case = []
    differences = []
    unresolved = []
    verified_sat = 0
    for task, pair in sorted(all_pairs.items()):
        left, right = pair["atlas-b"], pair["macro"]
        if left["B"] != right["B"] or left["b"] != right["b"] or left["objectiveKind"] != right["objectiveKind"]:
            raise ValueError("Matched domain differs: " + task)
        for method, row in pair.items():
            if row["status"] == "SAT":
                if row["verification"] != "PASSED":
                    differences.append(dict(task=task, kind="VERIFICATION", method=method, actual=row["verification"]))
                else:
                    verified_sat += 1
        decisive = left["status"] in {"SAT", "UNSAT"} and right["status"] in {"SAT", "UNSAT"}
        if decisive:
            if left["status"] != right["status"]:
                differences.append(dict(task=task, kind="STATUS", atlasB=left["status"], macro=right["status"]))
            elif left["status"] == "SAT" and (left["objectivePrimary"], left["objectiveSecondary"]) != (
                right["objectivePrimary"], right["objectiveSecondary"]):
                differences.append(dict(task=task, kind="OBJECTIVE",
                    atlasB=[left["objectivePrimary"], left["objectiveSecondary"]],
                    macro=[right["objectivePrimary"], right["objectiveSecondary"]]))
        else:
            unresolved.append(dict(task=task, atlasB=left["status"], macro=right["status"]))
        per_case.append(dict(task=task, family=task.split("/")[0], B=left["B"], b=left["b"],
            objectiveKind=left["objectiveKind"], atlasBStatus=left["status"], macroStatus=right["status"],
            atlasBPrimary=left["objectivePrimary"], atlasBSecondary=left["objectiveSecondary"],
            macroPrimary=right["objectivePrimary"], macroSecondary=right["objectiveSecondary"],
            atlasBVerification=left["verification"], macroVerification=right["verification"],
            atlasBTotalSec=left["totalSec"], macroTotalSec=right["totalSec"], bothDecisive=decisive))
    args.output.mkdir(parents=True)
    save_csv(args.output / "per-case.csv", per_case, list(per_case[0]))
    save_json(args.output / "disagreements.json", differences)
    save_json(args.output / "unresolved.json", unresolved)
    report = dict(totalCases=623, bothDecisive=623-len(unresolved), unresolved=len(unresolved),
                  disagreements=len(differences), verifiedSatRuns=verified_sat, source=source,
                  note="Official inputs are matched U-free derivatives; TIMEOUT/ERROR are unresolved, not agreements")
    save_json(args.output / "report.json", report)
    print(json.dumps(report, indent=2))


def install(args):
    directory = args.directory.resolve()
    load_plan(directory)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", args.unit):
        raise ValueError("Invalid systemd unit name")
    unit = pathlib.Path("/etc/systemd/system") / (args.unit + ".service")
    content = "\n".join(("[Unit]", "Description=MacroATLAS RQ1 tiny exhaustive experiment", "After=network.target", "",
        "[Service]", "Type=simple", "WorkingDirectory=" + str(ATLAS),
        "ExecStart=" + PYTHON + " " + str(pathlib.Path(__file__).resolve()) + " run " + str(directory),
        "Environment=PYTHONUNBUFFERED=1", "Restart=no", "KillMode=control-group", "TimeoutStopSec=15",
        "StandardOutput=append:" + str(directory / "logs/controller.log"),
        "StandardError=append:" + str(directory / "logs/controller.log"), "", "[Install]", "WantedBy=multi-user.target", ""))
    if unit.exists() and unit.read_text() != content:
        raise ValueError("Different RQ1 unit already installed")
    unit.write_text(content)
    subprocess.run(["systemctl", "daemon-reload"], check=True)
    print("Installed, not started:", unit)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser("prepare")
    make.add_argument("--output", type=pathlib.Path, required=True)
    make.add_argument("--count", type=int, default=1000)
    make.add_argument("--offset", type=int, default=0)
    make.add_argument("--seed", type=int, default=20260923)
    create = commands.add_parser("plan")
    create.add_argument("--dataset", type=pathlib.Path, required=True)
    create.add_argument("--output", type=pathlib.Path, required=True)
    create.add_argument("--workers", type=int, default=7)
    create.add_argument("--timeout", type=float, default=180)
    create.add_argument("--heap", default="2g")
    create.add_argument("--java", default=JAVA)
    create.add_argument("--gate", type=pathlib.Path, required=True)
    for name in ("run", "status", "summary", "install-service"):
        sub = commands.add_parser(name)
        sub.add_argument("directory", type=pathlib.Path)
    commands.choices["install-service"].add_argument("--unit", default=SERVICE)
    import_cmd = commands.add_parser("official")
    import_cmd.add_argument("--b2", type=pathlib.Path, required=True)
    import_cmd.add_argument("--b3", type=pathlib.Path, required=True)
    import_cmd.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare": prepare(args)
    elif args.command == "plan": plan(args)
    elif args.command == "run": run(args)
    elif args.command == "status": status(args.directory.resolve())
    elif args.command == "summary": summarize(args)
    elif args.command == "official": official(args)
    else: install(args)


if __name__ == "__main__":
    main()
