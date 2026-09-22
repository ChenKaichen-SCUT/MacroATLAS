"""Linux cgroup v2 evidence and CPU topology checks for isolated experiment workers."""
import json
import os
import pathlib


def cpu_set(text):
    result = set()
    for part in text.strip().replace(" ", ",").split(","):
        if not part:
            continue
        ends = part.split("-")
        first, last = int(ends[0]), int(ends[-1])
        if first < 0 or last < first or len(ends) > 2:
            raise ValueError("Invalid CPU range: " + part)
        result.update(range(first, last + 1))
    return result


def cpu_text(cpus):
    return ",".join(map(str, sorted(cpus)))


def topology():
    """Do not assign visible SMT siblings to competing workers."""
    available = set(os.sched_getaffinity(0))
    groups = set()
    for cpu in available:
        path = pathlib.Path("/sys/devices/system/cpu/cpu%d/topology/thread_siblings_list" % cpu)
        siblings = cpu_set(path.read_text()) & available
        groups.add(tuple(sorted(siblings)))
    return sorted(groups)


def allocate(groups, workers, reserved=1):
    if workers < 1 or len(groups) - reserved < workers or reserved < 1:
        raise ValueError("Insufficient physical core groups; reserve at least one for the OS/controller")
    slots = [[] for _ in range(workers)]
    count = ((len(groups) - reserved) // workers) * workers
    used = groups[reserved:reserved + count]
    for i, group in enumerate(used):
        slots[i % workers].extend(group)
    spare = groups[:reserved] + groups[reserved + count:]
    return [cpu_text(slot) for slot in slots], cpu_text(sum((list(g) for g in spare), []))


def current_cgroup():
    for line in pathlib.Path("/proc/self/cgroup").read_text().splitlines():
        if line.startswith("0::"):
            return pathlib.Path("/sys/fs/cgroup") / line[3:].lstrip("/")
    raise RuntimeError("Parallel workers require cgroup v2")


def snapshot(path):
    result = {"path": str(path)}
    for name in ["memory.max", "memory.swap.max", "memory.current", "memory.peak", "memory.events",
                 "memory.events.local", "memory.pressure", "cpu.stat", "cpu.pressure", "cpuset.cpus.effective", "io.stat"]:
        file = path / name
        if file.exists():
            result[name] = file.read_text().strip()
    return result


def oom_kills(evidence):
    values = dict(line.split() for line in evidence.get("memory.events", "").splitlines())
    return int(values.get("oom_kill", 0))


def check_worker(file, cpu, memory_mb):
    config = json.loads(file.read_text())
    path = current_cgroup()
    expected = cpu_set(config["cpus"])
    if path.name != config["unit"] + ".service":
        raise ValueError("Worker is not running in its registered systemd service")
    evidence = snapshot(path)
    if cpu_set(evidence["cpuset.cpus.effective"]) != expected or set(os.sched_getaffinity(0)) != expected:
        raise ValueError("Actual cpuset/affinity differs from worker allocation")
    if cpu_set(cpu or "") != expected or memory_mb != config["memoryMb"]:
        raise ValueError("Runner settings differ from registered allocation")
    if int(evidence["memory.max"]) != memory_mb * 1024 * 1024 or evidence["memory.swap.max"] != "0":
        raise ValueError("Hard cgroup memory/swap limits are missing")
    # Keep the lightweight controller alive while the native solver/JVM is the OOM victim.
    pathlib.Path("/proc/self/oom_score_adj").write_text("-900")
    return config, path, evidence


def reset_child_oom_score():
    pathlib.Path("/proc/self/oom_score_adj").write_text("0")
