#!/usr/bin/env python3
"""Retry only the two RQ1 exact jobs that exhausted the 5 GiB address-space cap.

The four proven-UNSAT sizes for each job are copied and checked, then solving
resumes at size five under a new, frozen memory limit. The original campaign is
never modified.
"""

from __future__ import annotations

import argparse
import collections
import concurrent.futures
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

from rq1_exact_campaign import CORE, SCRIPT as ORIGINAL_CONTROLLER, check_plan, formula, load, save, sha, utc
from rq1_exact_smt import check_size, parse_task


SCRIPT = Path(__file__).resolve()
OOM_TASKS = {'baseTest/0019.trace', 'baseTest/0040.trace'}


def verify_old_steps(job: Path, result: dict, count: int = 4) -> list[dict]:
    steps = result.get('steps', [])
    if len(steps) != count or [step['size'] for step in steps] != list(range(1, count + 1)):
        raise ValueError(f'Expected exactly {count} prior steps in {job}')
    for step in steps:
        if step['status'] != 'unsat':
            raise ValueError(f'Prior size {step["size"]} is not proven UNSAT in {job}')
        folder = job / f'size_{step["size"]:03d}'
        record = load(folder / 'record.json')
        query_hash = hashlib.sha256(gzip.decompress((folder / 'query.smt2.gz').read_bytes())).hexdigest()
        if (record['size'] != step['size'] or record['status'] != 'unsat'
                or record['querySha256'] != step['querySha256'] or query_hash != step['querySha256']):
            raise ValueError(f'Prior query/record mismatch in {folder}')
    return steps


def prepare(previous: Path, campaign: Path, memory_gib: int) -> None:
    if campaign.exists():
        raise ValueError('Destination campaign already exists')
    old = load(previous / 'plan.json')
    if sha(previous / 'plan.json') != (previous / 'plan.sha256').read_text().split()[0]:
        raise ValueError('Previous frozen plan checksum mismatch')
    for name, key in (('rq1_exact_smt.py', 'encodingSha256'),
                      ('rq1_exact_campaign.py', 'controllerSha256')):
        if sha(previous / 'code' / name) != old[key]:
            raise ValueError(f'Previous frozen code checksum mismatch: {name}')
    selected = [case for case in old['cases'] if case['task'] in OOM_TASKS]
    if {case['task'] for case in selected} != OOM_TASKS:
        raise ValueError('Expected two specific frozen OOM tasks')
    for case in selected:
        job = previous / 'jobs' / case['id']
        result = load(job / 'result.json')
        if result['status'] != 'UNKNOWN' or result.get('reason') != 'SMT_out of memory':
            raise ValueError(f'Previous job is not OOM: {case["task"]}')
        if result['steps'][-1]['size'] != 5 or result['steps'][-1]['reasonUnknown'] != 'out of memory':
            raise ValueError(f'Previous size-five outcome changed: {case["task"]}')
        verify_old_steps(job, {'steps': result['steps'][:4]})
        source = previous / 'inputs' / case['task']
        if sha(source) != case['inputSha256']:
            raise ValueError(f'Frozen input changed: {case["task"]}')

    campaign.mkdir(parents=True)
    (campaign / 'code').mkdir()
    for source in (CORE, ORIGINAL_CONTROLLER, SCRIPT):
        shutil.copy2(previous / 'code' / source.name if source != SCRIPT else source,
                     campaign / 'code' / source.name)
    for case in selected:
        source = previous / 'inputs' / case['task']
        target = campaign / 'inputs' / case['task']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        old_job = previous / 'jobs' / case['id']
        job = campaign / 'jobs' / case['id']
        job.mkdir(parents=True)
        for size in range(1, 5):
            shutil.copytree(old_job / f'size_{size:03d}', job / f'size_{size:03d}')
        save(job / 'inherited-from.json', {
            'previousCampaign': str(previous),
            'previousPlanSha256': sha(previous / 'plan.json'),
            'previousResultSha256': sha(old_job / 'result.json'),
            'inheritedUnsatSizes': [1, 2, 3, 4],
            'previousWallSec': load(old_job / 'result.json')['wallSec'],
        })
    plan = {**old, 'cases': selected, 'expectedCases': 2, 'createdUtc': utc(),
            'previousCampaign': str(previous),
            'previousPlanSha256': sha(previous / 'plan.json'),
            'caseTimeoutSec': old['caseTimeoutSec'],
            'solverTimeoutSec': old['solverTimeoutSec'],
            'memoryLimitGiB': memory_gib,
            'retryControllerSha256': sha(campaign / 'code' / SCRIPT.name),
            'resumeAtSize': 5, 'oneAttemptPerCase': True}
    save(campaign / 'plan.json', plan)
    (campaign / 'plan.sha256').write_text(sha(campaign / 'plan.json') + '  plan.json\n')
    save(campaign / 'state.json', {'status': 'READY', 'createdUtc': utc()})
    check_setup(campaign)


def check_setup(campaign: Path) -> dict:
    plan = check_plan(campaign)
    if sha(campaign / 'code' / SCRIPT.name) != plan['retryControllerSha256']:
        raise ValueError('Frozen retry controller checksum mismatch')
    if len(plan['cases']) != 2 or {x['task'] for x in plan['cases']} != OOM_TASKS:
        raise ValueError('Retry plan is not the two selected OOM tasks')
    for case in plan['cases']:
        task = parse_task(campaign / 'inputs' / case['task'], int(case['B']),
                          int(case['b']), case['category'])
        if task.source_sha256 != case['inputSha256']:
            raise ValueError(f'Frozen input checksum mismatch: {case["task"]}')
    return plan


def worker(campaign: Path, case_id: str) -> None:
    plan = check_setup(campaign)
    case = next(case for case in plan['cases'] if case['id'] == case_id)
    job = campaign / 'jobs' / case_id
    old_job = Path(plan['previousCampaign']) / 'jobs' / case_id
    if sha(old_job / 'result.json') != load(job / 'inherited-from.json')['previousResultSha256']:
        raise ValueError('Previous OOM result changed after preparation')
    old = load(old_job / 'result.json')
    steps = verify_old_steps(job, {'steps': old['steps'][:4]})
    task = parse_task(campaign / 'inputs' / case['task'], int(case['B']),
                      int(case['b']), case['category'])
    started = time.monotonic()
    final = None
    try:
        for size in range(5, min(task.B, plan['maxEncodedSize']) + 1):
            remaining = plan['caseTimeoutSec'] - (time.monotonic() - started)
            if remaining < 2:
                final = {'status': 'TIMEOUT', 'reason': 'CASE_DEADLINE'}
                break
            record = check_size(task, size, job / f'size_{size:03d}',
                                int(min(plan['solverTimeoutSec'], remaining - 1) * 1000))
            steps.append({key: record[key] for key in
                          ('size', 'status', 'wallSec', 'querySha256', 'reasonUnknown')})
            if record['status'] == 'sat':
                witness = load(job / f'size_{size:03d}' / 'witness.json')
                final = {'status': 'OPTIMAL', 'objectiveKind': 'MIN_EXPANDED_SIZE',
                         'objectivePrimary': 0, 'objectiveSecondary': size,
                         'witness': witness, 'formula': formula(witness),
                         'certificate': 'Sizes 1–4 inherited as verified UNSAT queries; '
                                        'all later smaller sizes UNSAT; this size SAT '
                                        'with independently checked witness'}
                break
            if record['status'] == 'unknown':
                final = {'status': 'TIMEOUT' if 'timeout' in record['reasonUnknown'].lower()
                         else 'UNKNOWN', 'reason': 'SMT_' + record['reasonUnknown']}
                break
        if final is None:
            final = ({'status': 'UNSAT', 'certificate': 'Every exact size 1..B is UNSAT'}
                     if min(task.B, plan['maxEncodedSize']) == task.B
                     else {'status': 'UNKNOWN', 'reason': 'SIZE_CAP'})
        final.update(task=case['task'], caseId=case_id, category=case['category'],
                     B=task.B, b=task.b, inputSha256=task.source_sha256,
                     steps=steps, checkedSizes=len(steps),
                     inheritedUnsatSizes=[1, 2, 3, 4],
                     wallSec=time.monotonic() - started,
                     previousAttemptWallSec=old['wallSec'], finishedUtc=utc())
        save(job / 'result.json', final)
    except Exception as error:
        save(job / 'result.json', {'task': case['task'], 'caseId': case_id,
                                  'status': 'UNKNOWN' if isinstance(error, MemoryError) else 'ERROR',
                                  'reason': f'{type(error).__name__}: {error}',
                                  'steps': steps, 'wallSec': time.monotonic() - started,
                                  'finishedUtc': utc()})
        raise


def launch(campaign: Path, plan: dict, case: dict, cpu: int) -> dict:
    job = campaign / 'jobs' / case['id']
    if (job / 'result.json').exists():
        return load(job / 'result.json')
    command = ['prlimit', f'--as={plan["memoryLimitGiB"] * 1024**3}', '--',
               'taskset', '-c', str(cpu), sys.executable,
               str(campaign / 'code' / SCRIPT.name), 'worker',
               '--campaign', str(campaign), '--id', case['id']]
    save(job / 'started.json', {'task': case['task'], 'command': command,
                                'startedUtc': utc(), 'attempt': 2})
    started = time.monotonic()
    with (job / 'stdout.log').open('w') as out, (job / 'stderr.log').open('w') as err:
        process = subprocess.Popen(command, stdout=out, stderr=err, start_new_session=True)
        try:
            code = process.wait(timeout=plan['caseTimeoutSec'] + 5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            code = process.wait()
            save(job / 'result.json', {'task': case['task'], 'caseId': case['id'],
                                       'status': 'TIMEOUT', 'reason': 'EXTERNAL_WALL_TIMEOUT',
                                       'wallSec': time.monotonic() - started,
                                       'finishedUtc': utc()})
    if not (job / 'result.json').exists():
        save(job / 'result.json', {'task': case['task'], 'caseId': case['id'],
                                   'status': 'ERROR',
                                   'reason': f'Worker exited {code} without result',
                                   'wallSec': time.monotonic() - started,
                                   'finishedUtc': utc()})
    return load(job / 'result.json')


def summarize(campaign: Path, plan: dict) -> None:
    previous = Path(plan['previousCampaign'])
    retry = {case['task']: load(campaign / 'jobs' / case['id'] / 'result.json')
             for case in plan['cases']}
    source_plan = load(previous / 'plan.json')
    rows = []
    for case in source_plan['cases']:
        old = load(previous / 'jobs' / case['id'] / 'result.json')
        result = retry.get(case['task'], old)
        rows.append({'task': case['task'], 'oracleStatus': result['status'],
                     'reason': result.get('reason', ''),
                     'objectivePrimary': result.get('objectivePrimary', ''),
                     'objectiveSecondary': result.get('objectiveSecondary', ''),
                     'formula': result.get('formula', ''),
                     'previousStatus': old['status'],
                     'previousReason': old.get('reason', ''),
                     'evidenceCampaign': str(campaign if case['task'] in retry else previous),
                     'evidencePath': f'jobs/{case["id"]}/result.json'})
    folder = campaign / 'summary'
    folder.mkdir(exist_ok=True)
    with (folder / 'merged-623.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    save(folder / 'summary.json', {'expectedCases': 623,
                                   'statuses': dict(collections.Counter(row['oracleStatus'] for row in rows)),
                                   'retryCases': len(retry),
                                   'retryStatuses': {task: result['status'] for task, result in retry.items()},
                                   'previousCampaign': str(previous),
                                   'completedUtc': utc()})


def run(campaign: Path) -> None:
    plan = check_setup(campaign)
    if load(campaign / 'state.json')['status'] != 'READY':
        raise ValueError('Campaign already started')
    save(campaign / 'state.json', {'status': 'RUNNING', 'startedUtc': utc(),
                                  'workers': 2, 'cpus': [2, 3],
                                  'memoryLimitGiBPerWorker': plan['memoryLimitGiB']})
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(launch, campaign, plan, case, cpu): case
                   for case, cpu in zip(plan['cases'], (2, 3))}
        for future in concurrent.futures.as_completed(futures):
            case = futures[future]
            result = future.result()
            print(utc(), case['task'], result['status'], result.get('reason', ''),
                  f'{result.get("wallSec", 0):.1f}s', flush=True)
    save(campaign / 'state.json', {'status': 'COMPLETE', 'finishedUtc': utc()})
    summarize(campaign, plan)


def status(campaign: Path) -> None:
    plan = check_setup(campaign)
    finished = []
    for case in plan['cases']:
        job = campaign / 'jobs' / case['id']
        result_path = job / 'result.json'
        if result_path.exists():
            result = load(result_path)
            finished.append(result['status'])
            print(f'{case["task"]}: {result["status"]} {result.get("reason", "")} '
                  f'checked through size {result.get("checkedSizes", "?")}')
        else:
            last = max((int(folder.name[-3:]) for folder in job.glob('size_[0-9][0-9][0-9]')
                        if (folder / 'record.json').exists()), default=4)
            print(f'{case["task"]}: RUNNING/PENDING, checked through size {last}')
    print(f'RQ1 OOM retry: {len(finished)}/2 | {dict(collections.Counter(finished))} '
          f'| state={load(campaign / "state.json")["status"]}')


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare')
    prep.add_argument('--previous', required=True, type=Path)
    prep.add_argument('--campaign', required=True, type=Path)
    prep.add_argument('--memory-gib', type=int, default=20)
    worker_parser = sub.add_parser('worker')
    worker_parser.add_argument('--campaign', required=True, type=Path)
    worker_parser.add_argument('--id', required=True)
    for name in ('run', 'status'):
        command = sub.add_parser(name)
        command.add_argument('--campaign', required=True, type=Path)
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare(args.previous.resolve(), args.campaign.resolve(), args.memory_gib)
    elif args.command == 'worker':
        worker(args.campaign.resolve(), args.id)
    elif args.command == 'run':
        run(args.campaign.resolve())
    else:
        status(args.campaign.resolve())


if __name__ == '__main__':
    main()
