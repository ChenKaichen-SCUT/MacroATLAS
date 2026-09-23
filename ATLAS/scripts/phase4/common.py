"""Shared deterministic manifests and result schema; standard library only."""
import hashlib
import csv
import json
import os
import pathlib
import platform
import subprocess

ATLAS = pathlib.Path(__file__).resolve().parents[2]
REPO = ATLAS.parent
STATUSES = {"SAT", "UNSAT", "TIMEOUT", "UNSUPPORTED", "FALLBACK", "ERROR", "VERIFICATION_FAILED"}
FIELDS = "task family variant repeat status outcome solverMode fallbackReason B b p K qStates fiberCount activeAnchors activeMacroEdges expandedSize objectiveKind objectivePrimary objectiveSecondary analysisSec registrySec fiberSec encodingSec solverSec decodeSec verifySec totalSec peakRssKb verification modelBytes vars backendTotalClauses error".split()
FIELDS += "searchNodeUniverse primaryVars semanticTypeCount selectedFiberCount meanRepresentativeLength maxRepresentativeLength optimizationPasses fallbackUsed backendTranslationCount".split()
FIELDS += "costStrategy unquotientedFiberCount encodedFiberCount costScope parseSec translationAndSolveSec totalInternalSec".split()
FIELDS += "inputTraceCount reducedTraceCount".split()


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def save_json(path, data):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    with temp.open("w") as f:
        f.write(json.dumps(data, indent=2, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())
    temp.replace(path)


def save_csv(path, rows, fields=FIELDS):
    """Atomically checkpoint complete rows so monitoring never sees a truncated CSV."""
    path = pathlib.Path(path)
    temp = path.with_name(path.name + ".tmp")
    with temp.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        f.flush()
        os.fsync(f.fileno())
    temp.replace(path)


def command(args, cwd=ATLAS):
    return subprocess.check_output(args, cwd=cwd, stderr=subprocess.STDOUT, text=True).strip()


def classpath():
    path = ATLAS / "target/runtime-classpath.txt"
    if not path.exists():
        raise RuntimeError("Build first: mvn -B verify dependency:build-classpath -Dmdep.outputFile=target/runtime-classpath.txt -DincludeScope=runtime")
    return os.pathsep.join([str(ATLAS / "target/classes"), str(ATLAS / "lib/AlloyMax-1.0.3.jar"), path.read_text().strip()])


def java_command(java="java", heap="4g"):
    return [java, "-Xms512m", "-Xmx" + heap, "-Djava.library.path=" + str(ATLAS / "lib"), "-cp", classpath(),
            "cmu.s3d.ltl.experiment.ExperimentMain"]


def environment(java="java"):
    return {"commit": command(["git", "rev-parse", "HEAD"]),
            "phase3Frozen": command(["git", "rev-parse", "macroatlas-phase3-frozen^{}"]),
            "dirty": bool(command(["git", "status", "--porcelain"])),
            "machine": platform.node(), "os": platform.platform(), "cpu": command(["lscpu"]),
            "ram": pathlib.Path("/proc/meminfo").read_text(), "java": command([java, "-version"]),
            "solver": "OpenWBOWeighted", "solverSha256": sha256(ATLAS / "lib/open-wbo"),
            "alloySha256": sha256(ATLAS / "lib/AlloyMax-1.0.3.jar"),
            "applicationSha256": digest([(p.relative_to(ATLAS / "target/classes").as_posix(), sha256(p))
                                         for p in sorted((ATLAS / "target/classes").rglob("*")) if p.is_file()]),
            "python": platform.python_version()}


def task_record(root, file):
    relative = file.relative_to(root).as_posix()
    return {"task": relative, "family": relative.split("/")[0], "sha256": sha256(file)}


def is_solved(row):
    status = row["outcome"] if row["status"] == "FALLBACK" else row["status"]
    return status == "UNSAT" or (status == "SAT" and row["verification"] in {"PASSED", "TRACE_PASSED"})
