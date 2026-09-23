#!/usr/bin/env python3
"""Record campaign memory and disk use without changing experiment results."""
import argparse
import csv
import datetime
import glob
import json
import os
import pathlib
import subprocess
import time


FIELDS = [
    "utc", "campaign", "completed", "host_mem_total_bytes", "host_mem_available_bytes",
    "root_disk_used_bytes", "root_disk_available_bytes", "campaign_disk_bytes",
    "workers_mem_current_bytes", "workers_mem_max_bytes", "workers_oom_kill_total",
    "worker_memory_json",
]


def meminfo():
    values = {}
    with open("/proc/meminfo") as source:
        for line in source:
            key, value = line.split(":", 1)
            values[key] = int(value.split()[0]) * 1024
    return values


def campaign_bytes(path):
    result = subprocess.run(["du", "-sb", str(path)], capture_output=True, text=True,
                            timeout=20, check=False)
    return int(result.stdout.split()[0]) if result.returncode == 0 else -1


def completed(path):
    count = 0
    for raw in glob.glob(str(path / "*" / "workers" / "*" / "raw.csv")):
        with open(raw, newline="") as source:
            count += max(0, sum(1 for _ in source) - 1)
    return count


def worker_memory(path):
    details = {}
    for config in glob.glob(str(path / "*" / "inputs" / "*" / "worker.json")):
        with open(config) as source:
            worker = json.load(source)
        unit = pathlib.Path("/sys/fs/cgroup/system.slice") / (worker["unit"] + ".service")
        if not unit.is_dir():
            continue

        def read(name):
            try:
                return (unit / name).read_text().strip()
            except FileNotFoundError:
                return ""

        events = dict(line.split() for line in read("memory.events").splitlines())
        details[worker["id"]] = {
            "current_bytes": int(read("memory.current") or 0),
            "limit_bytes": read("memory.max"),
            "oom_kill": int(events.get("oom_kill", 0)),
        }
    return details


def sample(path):
    memory = meminfo()
    fs = os.statvfs("/")
    workers = worker_memory(path)
    return {
        "utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "campaign": path.name,
        "completed": completed(path),
        "host_mem_total_bytes": memory["MemTotal"],
        "host_mem_available_bytes": memory["MemAvailable"],
        "root_disk_used_bytes": (fs.f_blocks - fs.f_bfree) * fs.f_frsize,
        "root_disk_available_bytes": fs.f_bavail * fs.f_frsize,
        "campaign_disk_bytes": campaign_bytes(path),
        "workers_mem_current_bytes": sum(w["current_bytes"] for w in workers.values()),
        "workers_mem_max_bytes": max((w["current_bytes"] for w in workers.values()), default=0),
        "workers_oom_kill_total": sum(w["oom_kill"] for w in workers.values()),
        "worker_memory_json": json.dumps(workers, separators=(",", ":")),
    }


def complete(path):
    try:
        return json.loads((path / "state.json").read_text())["status"] == "COMPLETE"
    except (FileNotFoundError, KeyError, ValueError):
        return False


def run(args):
    campaigns = [path.resolve() for path in args.campaign]
    for path in campaigns:
        if not path.is_dir():
            raise ValueError("Campaign does not exist: " + str(path))
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    new = not output.exists() or output.stat().st_size == 0
    end = time.monotonic() + args.duration
    with output.open("a", newline="", buffering=1) as destination:
        writer = csv.DictWriter(destination, fieldnames=FIELDS)
        if new:
            writer.writeheader()
        while True:
            for path in campaigns:
                writer.writerow(sample(path))
            if args.once or (args.until_complete and all(complete(path) for path in campaigns)):
                break
            if time.monotonic() >= end:
                break
            time.sleep(args.interval)


def summary(path):
    with path.open(newline="") as source:
        rows = list(csv.DictReader(source))
    for name in sorted({row["campaign"] for row in rows}):
        group = [row for row in rows if row["campaign"] == name]
        last = group[-1]
        gib = 1024 ** 3
        peak = lambda field: max(int(row[field]) for row in group) / gib
        available = min(int(row["host_mem_available_bytes"]) for row in group) / gib
        oom = max(int(row["workers_oom_kill_total"]) for row in group)
        print(f"{name}: {last['completed']} complete, {len(group)} samples, last {last['utc']}")
        print("  peak workers %.2f GiB total / %.2f GiB one; minimum host available %.2f GiB; OOM kills %d" %
              (peak("workers_mem_current_bytes"), peak("workers_mem_max_bytes"), available, oom))
        print("  peak campaign disk %.2f GiB; peak root disk used %.2f GiB" %
              (peak("campaign_disk_bytes"), peak("root_disk_used_bytes")))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    monitor = commands.add_parser("run")
    monitor.add_argument("--campaign", type=pathlib.Path, action="append", required=True)
    monitor.add_argument("--output", type=pathlib.Path, required=True)
    monitor.add_argument("--interval", type=float, default=30)
    monitor.add_argument("--duration", type=float, default=24 * 60 * 60)
    monitor.add_argument("--until-complete", action="store_true")
    monitor.add_argument("--once", action="store_true")
    report = commands.add_parser("summary")
    report.add_argument("csv", type=pathlib.Path)
    args = parser.parse_args()
    if args.command == "run":
        if args.interval <= 0 or args.duration <= 0:
            parser.error("Interval and duration must be positive")
        run(args)
    else:
        summary(args.csv)


if __name__ == "__main__":
    main()
