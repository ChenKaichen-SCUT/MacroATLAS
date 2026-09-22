#!/usr/bin/env python3
"""Plan, run, monitor and merge CPU/memory-isolated Phase 4 experiment workers."""
import argparse
import collections
import csv
import datetime
import fcntl
import json
import os
import pathlib
import random
import shutil
import signal
import subprocess
import sys
import tarfile
import time

from common import ATLAS, FIELDS, digest, environment, save_csv, save_json, sha256, task_record
from isolation import allocate, cpu_set, topology
from validate_results import validate


def read_json(path):
    return json.loads(pathlib.Path(path).read_text())


def timestamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def partition(records, count, seed):
    """Balance each family, keeping all variants/repeats of a task on one worker."""
    groups = collections.defaultdict(list)
    for record in records:
        groups[record["family"]].append(record)
    rng = random.Random(seed)
    slots = [[] for _ in range(count)]
    for family in sorted(groups):
        values = sorted(groups[family], key=lambda r: r["task"])
        rng.shuffle(values)
        for record in values:
            smallest = min(range(count), key=lambda i: (len(slots[i]), i))
            slots[smallest].append(record)
    return slots


def make_plan(a):
    output = a.output.resolve()
    if output.exists():
        raise ValueError("Campaign directory must be new")
    if a.workers < 1 or a.memory_mb < 1024 or a.repeats < 1 or a.timeout <= 0 or a.min_free_disk_gb < 1:
        raise ValueError("Invalid worker/memory/repeat/timeout setting")
    groups = topology()
    cpus, reserved = allocate(groups, a.workers)
    ram_kb = int(next(line.split()[1] for line in pathlib.Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemTotal:')))
    if a.workers * a.memory_mb > ram_kb / 1024 - a.reserve_memory_mb:
        raise ValueError("Worker memory reservations would oversubscribe RAM")
    env = environment(a.java)
    if env['dirty'] and not a.pilot:
        raise ValueError("Commit the deployment tools before planning formal runs")
    if not a.pilot:
        gate = read_json(a.gate)
        if gate.get('status') != 'PASSED' or any(gate.get(k) != env[k] for k in ['commit', 'java', 'applicationSha256', 'solverSha256', 'alloySha256']):
            raise ValueError("Run the correctness gate on this server/commit before planning")
    official = a.official.resolve()
    synthetic = a.synthetic.resolve() if a.synthetic else None
    selected_phases = a.phases
    if 'e8-synthetic' in selected_phases and synthetic is None:
        raise ValueError("--synthetic is required for e8-synthetic")
    selection = None
    if a.paper_fraction is not None:
        if 'e8-synthetic' in selected_phases:
            raise ValueError("A paper subset excludes synthetic tasks; select e3-original e4-matched e5-auto")
        from paper_subset import selection_manifest
        selection = selection_manifest(official, a.paper_fraction, a.seed)
    source_phases = [
        ('e3-original', 'original', ATLAS/'benchmark', official/'paper_tasks.txt', 1, False),
        ('e4-matched', 'matched', official/'matched_u_free', official/'matched/supported_tasks.txt', a.repeats, False),
        ('e5-auto', 'auto', ATLAS/'benchmark', official/'original_tasks.txt', 1, False),
    ]
    if synthetic:
        source_phases.append(('e8-synthetic', 'matched', synthetic/'matched_u_free', synthetic/'matched/supported_tasks.txt', a.repeats, True))
    source_phases = [p for p in source_phases if p[0] in selected_phases]
    if a.smoke_root:
        if not a.pilot:
            raise ValueError("Smoke workload must be labelled pilot")
        smoke = a.smoke_root.resolve()
        source_phases = [('smoke-matched', 'matched', smoke/'matched_u_free', smoke/'matched/supported_tasks.txt', 1, False)]
    plan = dict(version=1, createdUtc=timestamp(), environment=env, output=str(output),
                controllerUnit=a.controller_unit, cpuGroups=groups, reservedCpus=reserved,
                workers=a.workers, workerCpus=cpus, workerMemoryMb=a.memory_mb, reserveMemoryMb=a.reserve_memory_mb,
                heap=a.heap, java=str(pathlib.Path(shutil.which(a.java) or a.java).resolve()), python=sys.executable,
                timeoutSec=a.timeout, seed=a.seed, b=a.b, pilot=a.pilot, minFreeDiskGb=a.min_free_disk_gb,
                gate=str(a.gate.resolve()), phases=[],
                protocolAmendment='User requested parallel execution. Disjoint visible CPU sibling groups and hard memory limits; shared hardware interference cannot be eliminated.')
    campaign_id = digest(dict(output=str(output), commit=env['commit']))[:10]
    output.mkdir(parents=True)
    (output/'logs').mkdir()
    if selection:
        plan['paperSubset'] = selection
        save_json(output/'selection.json', selection)
        save_csv(output/'selection-counts.csv', selection['counts'], list(selection['counts'][0]))
    if a.gate.exists():
        shutil.copy2(a.gate, output/'correctness-gate.json')
        if a.gate.with_suffix('.log').exists():
            shutil.copy2(a.gate.with_suffix('.log'), output/'logs/correctness-gate.log')
    for name, suite, root, tasks, repeats, per_task in source_phases:
        names = tasks.read_text().splitlines()
        if not names or len(names) != len(set(names)):
            raise ValueError("Empty/duplicate task list: " + str(tasks))
        coverage = None
        if suite == 'matched':
            with tasks.with_name('coverage.csv').open() as f:
                all_rows = list(csv.DictReader(f))
            coverage = {r['task']: r for r in all_rows if r['supported'] == 'true'}
            if set(names) != set(coverage):
                raise ValueError("Source support list differs from analyzer coverage")
        if selection:
            selected_names = {r['task'] for r in selection['tasks']}
            names = [n for n in names if n in selected_names]
            if not names:
                raise ValueError("Selected phase has no eligible tasks: " + name)
        records = []
        for task in names:
            file = (root/task).resolve()
            file.relative_to(root.resolve())
            record = task_record(root.resolve(), file)
            if per_task:
                sidecar = read_json(file.with_suffix('.json'))
                record.update(B=int(sidecar['B']), b=int(sidecar['b']))
            records.append(record)
        phase = dict(id=name, suite=suite, root=str(root.resolve()), tasks=records, taskListHash=digest(records),
                     sourceTaskList=str(tasks), sourceTaskListSha256=sha256(tasks), repeats=repeats, perTaskBudgets=per_task, workers=[])
        for i, shard in enumerate(partition(records, a.workers, a.seed)):
            if not shard:
                continue
            worker_id = 'w%02d' % i
            folder = output/name/'inputs'/worker_id
            folder.mkdir(parents=True)
            (folder/'supported_tasks.txt').write_text(''.join(r['task']+'\n' for r in shard))
            if coverage is not None:
                save_csv(folder/'coverage.csv', [coverage[r['task']] for r in shard], list(next(iter(coverage.values()))))
            config = dict(id=worker_id, phase=name, campaign=str(output), campaignId=campaign_id,
                          cpus=cpus[i], memoryMb=a.memory_mb, unit='macroatlas-'+campaign_id+'-'+name+'-'+worker_id,
                          taskListHash=digest(shard), lockFile=str(folder/'worker.lock'))
            save_json(folder/'worker.json', config)
            (output/'logs'/(name+'-'+worker_id+'.log')).touch()
            phase['workers'].append(dict(config=config, configFile=str(folder/'worker.json'),
                                          tasks=str(folder/'supported_tasks.txt'), records=shard,
                                          output=str(output/name/'workers'/worker_id),
                                          log=str(output/'logs'/(name+'-'+worker_id+'.log'))))
        plan['phases'].append(phase)
    save_json(output/'plan.json', plan)
    (output/'plan.sha256').write_text(sha256(output/'plan.json')+'  plan.json\n')
    save_json(output/'state.json', dict(status='READY', updatedUtc=timestamp()))
    (output/'logs/controller.log').touch()
    # Exact inputs and source are retained even if generated working directories are later removed.
    with tarfile.open(output/'inputs.tar.gz', 'w:gz', compresslevel=1) as archive:
        for phase in plan['phases']:
            for record in phase['tasks']:
                file = pathlib.Path(phase['root'])/record['task']
                archive.add(file, arcname=phase['id']+'/'+record['task'])
                if phase['perTaskBudgets']:
                    archive.add(file.with_suffix('.json'), arcname=phase['id']+'/'+str(pathlib.Path(record['task']).with_suffix('.json')))
    subprocess.run(['git', 'bundle', 'create', str(output/'source.bundle'), 'HEAD', 'macroatlas-phase3-frozen'], cwd=ATLAS, check=True)
    save_json(output/'input-source-checksums.json', {name:sha256(output/name) for name in ['inputs.tar.gz', 'source.bundle', 'plan.json']})
    print(json.dumps(dict(campaign=str(output), workerCpus=cpus, reservedCpus=reserved,
                          memoryMb=a.memory_mb, phases=[(p['id'], len(p['tasks']), p['repeats']) for p in plan['phases']]), indent=2))


def load_plan(directory):
    directory = pathlib.Path(directory).resolve()
    plan = read_json(directory/'plan.json')
    if (directory/'plan.sha256').read_text().split()[0] != sha256(directory/'plan.json'):
        raise ValueError("Campaign plan changed after registration")
    if pathlib.Path(plan['output']) != directory:
        raise ValueError("Run the plan in its registered directory")
    for phase in plan['phases']:
        collected = []
        for worker in phase['workers']:
            if read_json(worker['configFile']) != worker['config']:
                raise ValueError("Worker registration changed")
            if pathlib.Path(worker['tasks']).read_text().splitlines() != [r['task'] for r in worker['records']]:
                raise ValueError("Worker task list changed")
            collected.extend(worker['records'])
        if sorted(collected, key=lambda r: r['task']) != sorted(phase['tasks'], key=lambda r: r['task']):
            raise ValueError("Shards do not cover the original task list exactly once")
    return plan


def service_state(unit):
    result = subprocess.check_output(['systemctl', 'show', unit, '--property=ActiveState,SubState,Result,ExecMainStatus'], text=True)
    return dict(line.split('=', 1) for line in result.splitlines() if '=' in line)


def worker_command(plan, phase, worker):
    config = worker['config']
    command = [plan['python'], str(ATLAS/'scripts/phase4/run.py'), '--root', phase['root'], '--tasks', worker['tasks'],
               '--suite', phase['suite'], '--output', worker['output'], '--repeats', str(phase['repeats']),
               '--timeout', str(plan['timeoutSec']), '--b', str(plan['b']), '--seed', str(plan['seed']),
               '--heap', plan['heap'], '--java', plan['java'], '--gate', plan['gate'], '--cpu', config['cpus'],
               '--memory-mb', str(config['memoryMb']), '--worker-config', worker['configFile'], '--resume']
    if plan['pilot']:
        command.append('--pilot')
    if phase['perTaskBudgets']:
        command.append('--task-budgets')
    properties = dict(WorkingDirectory=str(ATLAS), AllowedCPUs=config['cpus'], CPUAffinity=config['cpus'].replace(',', ' '),
                      MemoryMax=str(config['memoryMb']*1024*1024), MemorySwapMax='0', MemoryAccounting='yes', CPUAccounting='yes',
                      OOMPolicy='continue', KillMode='control-group', TimeoutStopSec='15', RemainAfterExit='yes',
                      BindsTo=plan['controllerUnit']+'.service', After=plan['controllerUnit']+'.service',
                      StandardOutput='append:'+worker['log'], StandardError='append:'+worker['log'])
    start = ['systemd-run', '--quiet', '--service-type=exec', '--unit='+config['unit']]
    for key, value in properties.items():
        start += ['--property='+key+'='+value]
    return start + command


def progress(plan):
    summary = []
    for phase in plan['phases']:
        variants = 1 if phase['suite'] == 'original' else 2
        for worker in phase['workers']:
            raw = pathlib.Path(worker['output'])/'raw.csv'
            rows = list(csv.DictReader(raw.open())) if raw.exists() else []
            summary.append(dict(phase=phase['id'], worker=worker['config']['id'], cpus=worker['config']['cpus'],
                                completed=len(rows), expected=len(worker['records'])*phase['repeats']*variants,
                                statuses=dict(collections.Counter(r['status'] for r in rows)), log=worker['log']))
    return summary


def merge_phase(plan, phase):
    destination = pathlib.Path(plan['output'])/phase['id']/'merged'
    if destination.exists():
        validate(destination)
        return destination
    rows, jobs, manifests, artifacts = [], [], [], []
    for worker in phase['workers']:
        directory = pathlib.Path(worker['output'])
        values, manifest = validate(directory)
        for key in ['commit', 'applicationSha256', 'java', 'solverSha256', 'alloySha256', 'machine']:
            if manifest[key] != plan['environment'][key]:
                raise ValueError("Worker environment differs from campaign: " + key)
        rows.extend(values)
        jobs.extend(read_json(directory/'expected_runs.json'))
        manifests.append(manifest)
        artifacts.extend((worker['config']['id']+'-'+path.parent.name, path.parent) for path in directory.glob('*/command.json'))
    expected = {(r['task'], v, repeat) for r in phase['tasks']
                for v in {'original':['original'], 'matched':['atlas-b','macro'], 'auto':['original','auto']}[phase['suite']]
                for repeat in range(1, phase['repeats']+1)}
    actual = [(r['task'], r['variant'], int(r['repeat'])) for r in rows]
    if len(actual) != len(set(actual)) or set(actual) != expected:
        raise ValueError("Merged task coverage is incomplete or duplicated")
    staging = destination.with_name('merge-'+str(time.time_ns()))
    staging.mkdir()
    manifest = dict(manifests[0], benchmarkRoot=phase['root'], taskListHash=phase['taskListHash'],
                    cpuAffinity='worker-specific; same worker for every task pair/repeat',
                    isolation=[w['config'] for w in phase['workers']], campaignPlanSha256=sha256(pathlib.Path(plan['output'])/'plan.json'))
    save_json(staging/'manifest.json', manifest)
    save_json(staging/'expected_runs.json', jobs)
    save_csv(staging/'raw.csv', rows)
    for name, path in artifacts:
        (staging/name).symlink_to(os.path.relpath(path, staging), target_is_directory=True)
    validate(staging)
    staging.rename(destination)
    return destination


def run_campaign(directory):
    plan = load_plan(directory)
    output = pathlib.Path(plan['output'])
    env = environment(plan['java'])
    for key in ['commit', 'machine', 'applicationSha256', 'java', 'solverSha256', 'alloySha256']:
        if env[key] != plan['environment'][key]:
            raise ValueError("Environment changed since planning: " + key)
    if env['dirty'] and not plan['pilot']:
        raise ValueError("Formal campaign requires clean source")
    controller = service_state(plan['controllerUnit'])
    if controller.get('ActiveState') != 'active':
        raise ValueError("Run through the registered controller service so worker lifetimes are bound to it")
    current_units = []
    def check_disk():
        free = shutil.disk_usage(output).free
        if free < plan.get('minFreeDiskGb', 8) * 1024**3:
            raise InterruptedError('LOW_DISK: %.2f GiB free; expand storage before resuming' % (free/1024**3))
    def interrupted(signum, frame):
        raise InterruptedError("Controller received signal %s" % signum)
    signal.signal(signal.SIGTERM, interrupted)
    (ATLAS/'results').mkdir(exist_ok=True)
    with (ATLAS/'results/.runner.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            for phase in plan['phases']:
                check_disk()
                print(timestamp(), 'START', phase['id'], flush=True)
                save_json(output/'state.json', dict(status='RUNNING', phase=phase['id'], updatedUtc=timestamp()))
                if (output/phase['id']/'merged').exists():
                    validate(output/phase['id']/'merged')
                    print(timestamp(), 'ALREADY_COMPLETE', phase['id'], flush=True)
                    continue
                current_units = [w['config']['unit'] for w in phase['workers']]
                for worker in phase['workers']:
                    unit = worker['config']['unit']
                    status = service_state(unit)
                    if status.get('SubState') == 'running':
                        raise ValueError("Worker is already running: " + unit)
                    subprocess.run(['systemctl', 'stop', unit], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    subprocess.run(['systemctl', 'reset-failed', unit], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    command = worker_command(plan, phase, worker)
                    save_json(pathlib.Path(worker['configFile']).with_name('launch-command.json'), command)
                    subprocess.run(command, check=True)
                last = 0
                while True:
                    check_disk()
                    states = {unit: service_state(unit) for unit in current_units}
                    # BindsTo can stop a worker before systemd delivers SIGTERM to its controller.
                    # A user-requested stop is an interruption, not an algorithm failure.
                    if service_state(plan['controllerUnit']).get('ActiveState') in {'deactivating', 'inactive'}:
                        raise InterruptedError('Controller service is stopping')
                    for unit, state in states.items():
                        if state.get('ActiveState') == 'failed' or state.get('Result') not in {'success', ''} or state.get('ActiveState') == 'inactive':
                            raise RuntimeError("Worker stopped/failed: %s %s" % (unit, state))
                    if time.monotonic()-last >= 15:
                        current = progress(plan)
                        save_json(output/'progress.json', dict(updatedUtc=timestamp(), workers=current))
                        selected = [w for w in current if w['phase'] == phase['id']]
                        print(timestamp(), phase['id'], ' '.join('%s=%d/%d' % (w['worker'], w['completed'], w['expected']) for w in selected), flush=True)
                        last = time.monotonic()
                    if all(s.get('SubState') == 'exited' for s in states.values()):
                        break
                    time.sleep(2)
                merged = merge_phase(plan, phase)
                from analyze import analyze
                analyze(merged)
                save_json(output/phase['id']/'complete.json', dict(status='COMPLETE', updatedUtc=timestamp(), rawSha256=sha256(merged/'raw.csv')))
                print(timestamp(), 'COMPLETE', phase['id'], flush=True)
                subprocess.run(['systemctl', 'stop']+current_units, check=True)
                current_units = []
            save_json(output/'state.json', dict(status='COMPLETE', updatedUtc=timestamp()))
            print(timestamp(), 'CAMPAIGN COMPLETE', flush=True)
            from paper_subset import report
            report(plan)
        except BaseException as error:
            save_json(output/'state.json', dict(status='INTERRUPTED' if isinstance(error, (InterruptedError, KeyboardInterrupt)) else 'FAILED',
                                               updatedUtc=timestamp(), error=str(error)))
            if isinstance(error, (InterruptedError, KeyboardInterrupt)):
                print(timestamp(), 'INTERRUPTED', str(error), flush=True)
                return
            raise
        finally:
            if current_units:
                subprocess.run(['systemctl', 'stop']+current_units, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def summarize(directory, finalize=False):
    plan = load_plan(directory)
    print(json.dumps(read_json(pathlib.Path(directory)/'state.json'), indent=2))
    for item in progress(plan):
        print('%-16s %s CPU=%-12s %5d/%-5d %s' % (item['phase'], item['worker'], item['cpus'], item['completed'], item['expected'], item['statuses']))
    if finalize:
        from analyze import analyze
        for phase in plan['phases']:
            merged = merge_phase(plan, phase)
            print(phase['id'], json.dumps(analyze(merged)))
        from paper_subset import report
        report(plan)


def install_service(directory):
    """Install only this campaign's controller; do not start or alter unrelated services."""
    if os.geteuid() != 0:
        raise ValueError("Installing the system service requires root")
    plan = load_plan(directory)
    unit = plan['controllerUnit']
    if any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in unit):
        raise ValueError("Invalid controller unit name")
    target = pathlib.Path('/etc/systemd/system')/(unit+'.service')
    # Current deployment paths deliberately avoid whitespace/systemd specifier expansion.
    paths = [plan['python'], str(ATLAS), plan['output']]
    if any(any(c.isspace() or c in '%\\"' for c in value) for value in paths):
        raise ValueError("Service deployment paths must not contain whitespace or systemd specifiers")
    content = '\n'.join([
        '[Unit]', 'Description=MacroATLAS isolated Phase 4 campaign', 'After=network.target', '',
        '[Service]', 'Type=simple', 'WorkingDirectory='+str(ATLAS),
        'ExecStart='+plan['python']+' '+str(ATLAS/'scripts/phase4/campaign.py')+' run '+plan['output'],
        'AllowedCPUs='+plan['reservedCpus'], 'CPUAffinity='+plan['reservedCpus'].replace(',', ' '),
        'Environment=PYTHONUNBUFFERED=1', 'Restart=no', 'KillMode=control-group', 'TimeoutStopSec=45',
        'StandardOutput=append:'+plan['output']+'/logs/controller.log',
        'StandardError=append:'+plan['output']+'/logs/controller.log', '', '[Install]', 'WantedBy=multi-user.target', ''])
    if target.exists() and target.read_text() != content:
        raise ValueError("Service already has a different plan; use a new controller unit")
    target.write_text(content)
    save_json(pathlib.Path(directory)/'controller-service.json', dict(path=str(target), content=content))
    subprocess.run(['systemctl', 'daemon-reload'], check=True)
    print('Installed, not started:', unit+'.service')


def archive_campaign(directory, destination):
    """Archive only quiescent campaigns so a backup never silently drops live writes."""
    plan = load_plan(directory)
    if service_state(plan['controllerUnit']).get('ActiveState') in {'active', 'activating', 'deactivating'}:
        raise ValueError("Stop the campaign before archiving, or wait until it completes")
    for phase in plan['phases']:
        for worker in phase['workers']:
            if service_state(worker['config']['unit']).get('SubState') == 'running':
                raise ValueError("Worker still running")
    destination = destination.resolve()
    if destination.exists() or destination.is_relative_to(pathlib.Path(plan['output'])):
        raise ValueError("Archive must be new and outside the campaign directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(destination, 'w:gz', compresslevel=1) as archive:
        archive.add(plan['output'], arcname=pathlib.Path(plan['output']).name)
    checksum = sha256(destination)
    destination.with_name(destination.name+'.sha256').write_text(checksum+'  '+destination.name+'\n')
    print(destination, checksum)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    commands = p.add_subparsers(dest='command', required=True)
    create = commands.add_parser('plan')
    create.add_argument('--output', type=pathlib.Path, required=True)
    create.add_argument('--official', type=pathlib.Path, required=True)
    create.add_argument('--synthetic', type=pathlib.Path)
    create.add_argument('--phases', nargs='+', choices=['e3-original', 'e4-matched', 'e5-auto', 'e8-synthetic'],
                        default=['e3-original', 'e4-matched', 'e5-auto', 'e8-synthetic'])
    create.add_argument('--paper-fraction', type=float, help='Outcome-independent stratified subset of paper tasks')
    create.add_argument('--workers', type=int, required=True)
    create.add_argument('--memory-mb', type=int, default=16384)
    create.add_argument('--reserve-memory-mb', type=int, default=4096)
    create.add_argument('--min-free-disk-gb', type=float, default=8)
    create.add_argument('--repeats', type=int, choices=[1], default=1,
                        help='One run per task/algorithm under the current exploratory protocol')
    create.add_argument('--timeout', type=float, default=180)
    create.add_argument('--seed', type=int, default=20260922)
    create.add_argument('--b', type=int, default=2)
    create.add_argument('--heap', default='4g')
    create.add_argument('--java', default='java')
    create.add_argument('--gate', type=pathlib.Path, default=ATLAS/'generated/phase4-gate.json')
    create.add_argument('--controller-unit', default='macroatlas-phase4')
    create.add_argument('--pilot', action='store_true')
    create.add_argument('--smoke-root', type=pathlib.Path)
    run = commands.add_parser('run');run.add_argument('directory', type=pathlib.Path)
    status = commands.add_parser('status');status.add_argument('directory', type=pathlib.Path)
    summary = commands.add_parser('summarize');summary.add_argument('directory', type=pathlib.Path)
    install = commands.add_parser('install-service');install.add_argument('directory', type=pathlib.Path)
    archive = commands.add_parser('archive');archive.add_argument('directory', type=pathlib.Path);archive.add_argument('--output', type=pathlib.Path, required=True)
    a = p.parse_args()
    if a.command == 'plan': make_plan(a)
    elif a.command == 'run': run_campaign(a.directory)
    elif a.command == 'install-service': install_service(a.directory)
    elif a.command == 'archive': archive_campaign(a.directory, a.output)
    else: summarize(a.directory, a.command == 'summarize')


if __name__ == '__main__':
    main()
