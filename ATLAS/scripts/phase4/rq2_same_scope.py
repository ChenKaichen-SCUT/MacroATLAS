#!/usr/bin/env python3
"""One-attempt, paired, same-expanded-size-scope CNF translation experiment."""
import argparse
import collections
import concurrent.futures
import csv
import datetime
import fcntl
import hashlib
import json
import math
import os
import pathlib
import signal
import statistics
import subprocess
import tarfile
import time

from common import ATLAS, classpath, sha256
from isolation import allocate, topology

JAVA = pathlib.Path('/srv/macroatlas/jdks/jdk8u462-b08/bin/java')
JAVAC = JAVA.with_name('javac')
JAR = ATLAS / 'lib/AlloyMax-1.0.3.jar'
MODES = ('atlas-b', 'macro')
SCOPES = (5, 7, 9, 11, 15)
SOURCE = pathlib.Path('/srv/macroatlas/experiments/rq2-e4-623/summary/rq2_paper_data.csv')
IMPORTS = pathlib.Path('/srv/macroatlas/imports')


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def save(path, obj):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(obj, indent=2, sort_keys=True) + '\n')
    temp.replace(path)


def read(path):
    return json.loads(pathlib.Path(path).read_text())


def table(path):
    with pathlib.Path(path).open(newline='') as f:
        return list(csv.DictReader(f))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def group(row):
    f = row['family']
    if f == 'voting_machine': return 'nnf_template'
    if f == 'robot': return 'repair'
    if f == 'peterson': return 'required'
    if f == 'weakening': return 'weakening_b' + row['b']
    if row['qStates'] == '1': return 'plain'
    raise ValueError('Unclassified source task: ' + row['task'])


def selected(rows):
    quotas = {'plain': 80, 'nnf_template': 10, 'repair': 20,
              'required': 30, 'weakening_b2': 30, 'weakening_b3': 30}
    buckets = collections.defaultdict(list)
    for row in rows:
        if int(row['B']) >= 5:
            buckets[group(row)].append(row)
    selection = []
    for category, quota in quotas.items():
        pool = sorted(buckets[category], key=lambda r: digest((r['batch'] + '/' + r['task'] + '/RQ2B').encode()))
        if len(pool) < quota: raise ValueError('Insufficient ' + category)
        if category == 'plain':
            # Spread the unconstrained stratum over all six source families.
            families = sorted({r['family'] for r in pool})
            parts = {f: [r for r in pool if r['family'] == f] for f in families}
            pool = []
            while any(parts.values()):
                for f in families:
                    if parts[f]: pool.append(parts[f].pop(0))
        used = set()
        desired = [5, 7, 5, 9, 5, 11, 5, 15]
        for i in range(quota):
            scope = desired[i % len(desired)]
            eligible = next((r for r in pool if (r['batch'], r['task']) not in used and int(r['B']) >= scope), None)
            if eligible is None:
                scope = max((s for s in SCOPES if s <= scope and any((r['batch'], r['task']) not in used and int(r['B']) >= s for r in pool)), default=0)
                eligible = next((r for r in pool if (r['batch'], r['task']) not in used and int(r['B']) >= scope), None)
            if eligible is None: raise ValueError('Cannot satisfy scope selection for ' + category)
            used.add((eligible['batch'], eligible['task']))
            selection.append((eligible, category, scope))
    if len(selection) != 200 or len({(r['batch'], r['task']) for r, _, _ in selection}) != 200:
        raise ValueError('Expected 200 unique case/scope pairs')
    return selection


def remaining(rows, completed_plan, source_sha256):
    """Cover every source case omitted by the frozen 200-case campaign."""
    old_jobs = completed_plan['jobs']
    if len(old_jobs) != 200 or completed_plan['attemptsPerMethodCaseScope'] != 1:
        raise ValueError('Expected the frozen 200-case, one-attempt plan')
    old = {(job['batch'], job['task']): job for job in old_jobs}
    source = {(row['batch'], row['task']): row for row in rows}
    if len(old) != 200 or len(source) != 623 or not set(old) <= set(source):
        raise ValueError('Source and completed-plan task identities differ')
    for key, job in old.items():
        if job['inputSha256'] != source[key]['inputSha256']:
            raise ValueError('Completed-plan input differs: ' + str(key))
    if completed_plan['sourceSha256'] != source_sha256:
        raise ValueError('Completed plan is not based on the frozen 623-case table')
    omitted = sorted((row for row in rows if (row['batch'], row['task']) not in old),
                     key=lambda row: digest((row['batch'] + '/' + row['task'] + '/RQ2B').encode()))
    if len(omitted) != 423:
        raise ValueError('Expected exactly 423 omitted cases')
    # Retain the earlier weighted scope grid.  Original sampling excluded B<5;
    # those cases use their actual bound rather than silently disappearing.
    desired = (5, 7, 5, 9, 5, 11, 5, 15)
    picks = []
    for index, row in enumerate(omitted):
        bound = int(row['B'])
        if bound < 1: raise ValueError('Invalid B for ' + row['task'])
        candidate = desired[index % len(desired)]
        scope = max((s for s in SCOPES if s <= candidate and s <= bound), default=bound)
        if scope > bound: raise ValueError('Scope exceeds B')
        picks.append((row, group(row), scope))
    return picks


def plan(args):
    output = args.output.resolve()
    if output.exists(): raise ValueError('Output directory exists')
    if args.workers < 1 or args.emit_timeout <= 0 or args.translate_timeout <= 0:
        raise ValueError('Invalid time/worker settings')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ATLAS, text=True).strip()
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=ATLAS, text=True).strip():
        raise ValueError('Commit code before making formal plan')
    rows = table(args.source)
    if len(rows) != 623: raise ValueError('Expected 623 frozen E4 source rows')
    completed = None
    if args.exclude_plan:
        completed_path = args.exclude_plan.resolve()
        completed = read(completed_path)
        if read(completed_path.parent / 'state.json')['status'] != 'COMPLETE':
            raise ValueError('Frozen 200-case campaign is not complete')
        picks = remaining(rows, completed, sha256(args.source))
    else:
        picks = selected(rows)
    cpus, reserved = allocate(topology(), args.workers)
    output.mkdir(parents=True)
    (output / 'inputs').mkdir()
    classes = output / 'classes'
    classes.mkdir()
    subprocess.run([str(JAVAC), '-cp', str(JAR), '-d', str(classes),
                    str(ATLAS / 'scripts/phase4/Rq2Translate.java')], check=True)
    archives = {}
    e4 = {}
    e4_hashes = {}
    for batch in ('b2', 'b3'):
        path = args.imports / ('full-e4-' + batch) / 'inputs.tar.gz'
        archives[batch] = {'path': str(path.resolve()), 'sha256': sha256(path)}
        raw_path = args.imports / ('full-e4-' + batch) / 'e4-matched/merged/raw.csv'
        e4_hashes[batch] = {'path': str(raw_path.resolve()), 'sha256': sha256(raw_path)}
        for item in table(raw_path):
            if item['variant'] == 'macro':
                key = (batch, item['task'])
                if key in e4: raise ValueError('Duplicate E4 Macro record')
                e4[key] = item
    jobs = []
    with tarfile.open(archives['b2']['path']) as b2, tarfile.open(archives['b3']['path']) as b3:
        opened = {'b2': b2, 'b3': b3}
        for row, category, scope in picks:
            batch, task = row['batch'], row['task']
            raw = opened[batch].extractfile('e4-matched/' + task).read()
            if digest(raw) != row['inputSha256']: raise ValueError('Input checksum mismatch: ' + task)
            source_result = e4[batch, task]
            jid = batch + '-' + digest((batch + '\0' + task + '\0' + str(scope)).encode())[:16]
            relative = pathlib.Path(batch) / jid / 'input.trace'
            dest = output / 'inputs' / relative
            dest.parent.mkdir(parents=True)
            dest.write_bytes(raw)
            jobs.append({'jobId': jid, 'input': str(dest), 'inputSha256': digest(raw),
                         'batch': batch, 'task': task, 'family': row['family'], 'category': category,
                         'B': int(row['B']), 'b': int(row['b']), 'p': int(row['p']),
                         'K': int(row['K']), 'qStates': int(row['qStates']),
                         'objectiveKind': row['objectiveKind'], 'constraintFeatures': row['constraintFeatures'],
                         'scope': scope, 'e4AtlasStatus': row['atlasE4Status'],
                         'e4MacroStatus': row['macroE4Status'],
                         'activeAnchors': row['activeAnchors'],
                         'e4MacroExpandedSize': int(source_result['expandedSize']) if source_result['status'] == 'SAT' else None,
                         'numAP': int(row['numAP']), 'positiveTraces': int(row['positiveTraces']),
                         'negativeTraces': int(row['negativeTraces'])})
    data = {'schemaVersion': 1, 'createdUtc': now(), 'commit': commit,
            'sourceCsv': str(args.source.resolve()), 'sourceSha256': sha256(args.source),
            'sourceArchives': archives, 'e4RawFiles': e4_hashes,
            'collectorSha256': sha256(__file__),
            'translatorSourceSha256': sha256(ATLAS / 'scripts/phase4/Rq2Translate.java'),
            'translatorClassesSha256': {p.name: sha256(p) for p in classes.glob('*.class')},
            'applicationClassesSha256': digest(json.dumps([(str(p.relative_to(ATLAS / 'target/classes')), sha256(p))
                                                   for p in sorted((ATLAS / 'target/classes').rglob('*.class'))],
                                                  separators=(',', ':')).encode()),
            'runtimeClasspathSha256': sha256(ATLAS / 'target/runtime-classpath.txt'),
            'alloySha256': sha256(JAR), 'java': str(args.java.resolve()),
            'javaHeap': args.heap, 'emitTimeoutSec': args.emit_timeout,
            'translateTimeoutSec': args.translate_timeout, 'workers': args.workers,
            'workerCpus': cpus, 'reservedCpus': reserved,
            'scopeMeaning': 'expanded formula size <= s for both encodings',
            'objective': 'minimum expanded size; repair primary objective omitted on both sides',
            'selection': ('all 423 cases omitted by frozen 200-case plan; SHA-256 order; '
                          'weighted scope grid 5/7/5/9/5/11/5/15 capped at B; B<5 uses B'
                          if completed else
                          'deterministic SHA-256 stratification; six quotas 80/10/20/30/30/30; one scope per unique case'),
            'expectedCases': len(jobs),
            'attemptsPerMethodCaseScope': 1, 'jobs': jobs}
    if completed:
        data['completedPlan'] = {'path': str(completed_path), 'sha256': sha256(completed_path),
                                 'statePath': str(completed_path.parent / 'state.json'),
                                 'summaryPath': str(completed_path.parent / 'summary'),
                                 'sourceCommit': completed['commit']}
    save(output / 'plan.json', data)
    (output / 'plan.sha256').write_text(sha256(output / 'plan.json') + '  plan.json\n')
    save(output / 'state.json', {'status': 'READY', 'updatedUtc': now()})
    (output / 'logs').mkdir()
    (output / 'logs' / 'controller.log').touch()
    print('Planned', len(jobs), 'unique pairs /', len(jobs) * 2, 'translations')
    print('Scope counts:', dict(collections.Counter(j['scope'] for j in jobs)))
    print('Category counts:', dict(collections.Counter(j['category'] for j in jobs)))
    print('Workers:', cpus, 'reserved:', reserved)


def load_plan(directory):
    directory = directory.resolve()
    if sha256(directory / 'plan.json') != (directory / 'plan.sha256').read_text().split()[0]:
        raise ValueError('Plan checksum changed')
    data = read(directory / 'plan.json')
    if subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ATLAS, text=True).strip() != data['commit']:
        raise ValueError('Application commit changed')
    if sha256(JAR) != data['alloySha256']:
        raise ValueError('Alloy binary changed')
    if sha256(ATLAS / 'target/runtime-classpath.txt') != data['runtimeClasspathSha256']:
        raise ValueError('Runtime classpath changed')
    current_classes = digest(json.dumps([(str(p.relative_to(ATLAS / 'target/classes')), sha256(p))
                                         for p in sorted((ATLAS / 'target/classes').rglob('*.class'))],
                                        separators=(',', ':')).encode())
    if current_classes != data['applicationClassesSha256']:
        raise ValueError('Application classes changed')
    if sha256(__file__) != data['collectorSha256']:
        raise ValueError('Collector changed')
    if {p.name: sha256(p) for p in (directory / 'classes').glob('*.class')} != data['translatorClassesSha256']:
        raise ValueError('Translator classes changed')
    if len(data['jobs']) != data.get('expectedCases', 200) or data['attemptsPerMethodCaseScope'] != 1:
        raise ValueError('Plan protocol changed')
    if data.get('completedPlan'):
        old = data['completedPlan']
        if sha256(old['path']) != old['sha256']:
            raise ValueError('Completed 200-case plan changed')
        if read(old['statePath'])['status'] != 'COMPLETE':
            raise ValueError('Completed 200-case campaign is not complete')
        rows = table(data['sourceCsv'])
        expected = remaining(rows, read(old['path']), data['sourceSha256'])
        actual = {(job['batch'], job['task']): job['scope'] for job in data['jobs']}
        if actual != {(row['batch'], row['task']): scope for row, _, scope in expected}:
            raise ValueError('423-case complement or scope assignments changed')
    if sha256(data['sourceCsv']) != data['sourceSha256']:
        raise ValueError('Frozen source CSV changed')
    for entry in data['sourceArchives'].values():
        if sha256(entry['path']) != entry['sha256']:
            raise ValueError('Frozen input archive changed')
    for entry in data['e4RawFiles'].values():
        if sha256(entry['path']) != entry['sha256']:
            raise ValueError('Frozen E4 raw results changed')
    return data


def method_path(directory, job, mode):
    return directory / 'jobs' / job['jobId'] / mode


def execute(command, cwd, out, err, timeout):
    began = time.monotonic()
    with out.open('w') as stdout, err.open('w') as stderr:
        proc = subprocess.Popen(command, cwd=cwd, stdout=stdout, stderr=stderr, start_new_session=True)
        try:
            code = proc.wait(timeout=timeout)
            return 'OK' if code == 0 else 'ERROR', time.monotonic() - began
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
            return 'TIMEOUT', time.monotonic() - began


def do_method(directory, data, job, mode, cpu):
    folder = method_path(directory, job, mode)
    final = folder / 'record.json'
    if final.exists(): return read(final)
    if folder.exists():
        record = {'status': 'INTERRUPTED_UNRECORDED', 'attempt': 1,
                  'error': 'Started attempt has no final record; never relaunched automatically'}
        save(final, record)
        return record
    folder.mkdir(parents=True)
    save(folder / 'started.json', {'attempt': 1, 'startedUtc': now(), 'commit': data['commit'],
                                  'inputSha256': job['inputSha256'], 'scope': job['scope'],
                                  'solverInvoked': False})
    wall_start = time.monotonic()
    record = {'attempt': 1, 'status': 'ERROR', 'scope': job['scope'],
              'primaryVars': None, 'vars': None, 'backendTotalClauses': None,
              'modelBytes': None, 'modelSha256': '', 'parseSec': None,
              'translationSec': None, 'emissionSec': None, 'error': '',
              'solverInvoked': False}
    try:
        if sha256(job['input']) != job['inputSha256']:
            raise ValueError('Input checksum mismatch')
        base = ['taskset', '-c', cpu, data['java'], '-XX:ActiveProcessorCount=2',
                '-Xms256m', '-Xmx' + data['javaHeap'], '-Djava.library.path=' + str(ATLAS / 'lib')]
        emit = base + ['-cp', classpath(), 'cmu.s3d.ltl.experiment.ExperimentMain',
                       '--mode', 'emit-scope', '--variant', mode, '--file', job['input'],
                       '--output', str(folder), '--B', str(job['B']), '--b', str(job['b']),
                       '--scope', str(job['scope'])]
        state, elapsed = execute(emit, ATLAS, folder / 'emit.stdout', folder / 'emit.stderr', data['emitTimeoutSec'])
        record['emissionSec'] = elapsed
        if state != 'OK':
            record['status'] = 'EMIT_' + state
            record['error'] = (folder / 'emit.stderr').read_text(errors='replace')[-2000:]
        else:
            info = read(folder / 'model-info.json')
            if info['costScope'] != job['scope'] or info['variant'] != mode or info['solverInvoked'] is not False:
                raise ValueError('Emitted model metadata mismatch')
            model = folder / 'model.als'
            record['modelBytes'] = model.stat().st_size
            record['modelSha256'] = sha256(model)
            translate = base + ['-Djava.io.tmpdir=' + str(folder), '-cp',
                                str(directory / 'classes') + ':' + str(JAR), 'Rq2Translate', str(model)]
            state, elapsed = execute(translate, ATLAS, folder / 'translate.stdout',
                                     folder / 'translate.stderr', data['translateTimeoutSec'])
            record['translationSec'] = elapsed
            if state != 'OK':
                record['status'] = 'TRANSLATION_' + state
                record['error'] = (folder / 'translate.stderr').read_text(errors='replace')[-2000:]
            else:
                metric = json.loads((folder / 'translate.stdout').read_text().strip())
                if metric['solverInvoked'] is not False or metric['status'] != 'TRANSLATED_ONLY':
                    raise ValueError('Translator did not stop before MaxSAT')
                record.update({k: metric[k] for k in ('primaryVars', 'vars', 'backendTotalClauses', 'parseSec')})
                record['status'] = 'TRANSLATED_ONLY'
    except Exception as exc:
        record['status'] = 'ERROR'
        record['error'] = repr(exc)
    record['wallSec'] = time.monotonic() - wall_start
    save(final, record)
    print(now(), job['category'], job['batch'], job['task'], 's=' + str(job['scope']), mode,
          record['status'], record['vars'], record['backendTotalClauses'], flush=True)
    return record


def progress(directory):
    data = read(directory / 'plan.json')
    counts = collections.Counter()
    statuses = {mode: collections.Counter() for mode in MODES}
    paired = 0
    for job in data['jobs']:
        ready = 0
        for mode in MODES:
            final = method_path(directory, job, mode) / 'record.json'
            if final.exists():
                counts[mode] += 1
                statuses[mode][read(final)['status']] += 1
                ready += 1
        if ready == 2: paired += 1
    state = read(directory / 'state.json')['status']
    print('RQ2 same-scope pairs %d/%d | ATLAS-B %d/%d | MacroATLAS %d/%d | state=%s' %
          (paired, len(data['jobs']), counts['atlas-b'], len(data['jobs']),
           counts['macro'], len(data['jobs']), state))
    for mode in MODES: print(mode, dict(statuses[mode]))
    return paired


def run(args):
    directory = args.directory.resolve()
    with (directory / 'controller.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        data = load_plan(directory)
        if read(directory / 'state.json')['status'] == 'COMPLETE':
            progress(directory)
            return
        save(directory / 'state.json', {'status': 'RUNNING', 'updatedUtc': now()})
        try:
            def worker(index):
                for offset, job in enumerate(data['jobs']):
                    if offset % data['workers'] != index: continue
                    for mode in MODES:
                        do_method(directory, data, job, mode, data['workerCpus'][index])
            with concurrent.futures.ThreadPoolExecutor(max_workers=data['workers']) as pool:
                for future in concurrent.futures.as_completed([pool.submit(worker, i) for i in range(data['workers'])]):
                    future.result()
            paired = progress(directory)
            if paired != len(data['jobs']): raise ValueError('Missing pairs')
            summarize(directory)
            save(directory / 'state.json', {'status': 'COMPLETE', 'completedPairs': paired, 'updatedUtc': now()})
        except BaseException as exc:
            save(directory / 'state.json', {'status': 'FAILED', 'error': repr(exc), 'updatedUtc': now()})
            raise


def write_csv(path, rows):
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def distribution(values):
    xs = sorted(x for x in values if x is not None and math.isfinite(x))
    return {'n': len(xs), 'median': statistics.median(xs) if xs else None,
            'min': xs[0] if xs else None, 'max': xs[-1] if xs else None}


def summarize(directory):
    data = load_plan(directory)
    runs, pairs = [], []
    for job in data['jobs']:
        result = {}
        for mode in MODES:
            final = method_path(directory, job, mode) / 'record.json'
            if not final.exists(): raise ValueError('Missing record: ' + str(final))
            rec = read(final)
            result[mode] = rec
            runs.append({**{k: job[k] for k in ('batch', 'task', 'family', 'category', 'B', 'b', 'p', 'K',
                        'qStates', 'objectiveKind', 'constraintFeatures', 'scope', 'inputSha256', 'numAP',
                        'positiveTraces', 'negativeTraces')}, 'method': mode, **rec})
        a, m = result['atlas-b'], result['macro']
        paired = a['status'] == m['status'] == 'TRANSLATED_ONLY'
        pairs.append({**{k: job[k] for k in ('batch', 'task', 'family', 'category', 'B', 'b', 'p', 'K',
                      'qStates', 'objectiveKind', 'constraintFeatures', 'scope', 'inputSha256', 'numAP',
                      'positiveTraces', 'negativeTraces', 'e4AtlasStatus', 'e4MacroStatus', 'activeAnchors',
                      'e4MacroExpandedSize')},
                      'B_over_K': job['B'] / job['K'],
                      'activeAnchors_over_expandedSize': (int(job['activeAnchors']) / job['e4MacroExpandedSize']
                          if job['e4MacroExpandedSize'] and job['activeAnchors'] else ''),
                      'atlasStatus': a['status'], 'macroStatus': m['status'], 'pairedTranslated': paired,
                      'atlasVars': a['vars'], 'macroVars': m['vars'],
                      'atlasClauses': a['backendTotalClauses'], 'macroClauses': m['backendTotalClauses'],
                      'C_V': a['vars'] / m['vars'] if paired and m['vars'] else '',
                      'C_C': a['backendTotalClauses'] / m['backendTotalClauses'] if paired and m['backendTotalClauses'] else '',
                      'atlasWallSec': a['wallSec'], 'macroWallSec': m['wallSec'],
                      'atlasModelSha256': a['modelSha256'], 'macroModelSha256': m['modelSha256']})
    output = directory / 'summary'
    output.mkdir(exist_ok=True)
    write_csv(output / 'rq2_same_scope_per_run.csv', runs)
    write_csv(output / 'rq2_same_scope_paper_data.csv', pairs)
    report = {'cases': len(pairs), 'runs': len(runs), 'completePairs': sum(p['pairedTranslated'] for p in pairs),
              'scopeCounts': dict(collections.Counter(p['scope'] for p in pairs)),
              'categoryCounts': dict(collections.Counter(p['category'] for p in pairs)),
              'statuses': {mode: dict(collections.Counter(r['status'] for r in runs if r['method'] == mode)) for mode in MODES},
              'C_V': distribution(p['C_V'] for p in pairs if p['pairedTranslated']),
              'C_C': distribution(p['C_C'] for p in pairs if p['pairedTranslated']),
              'B_over_K': distribution(p['B_over_K'] for p in pairs),
              'activeAnchors_over_expandedSize': distribution(p['activeAnchors_over_expandedSize']
                  for p in pairs if p['activeAnchors_over_expandedSize'] != ''),
              'byCategory': {c: {'pairs': len([p for p in pairs if p['category'] == c]),
                                  'complete': len([p for p in pairs if p['category'] == c and p['pairedTranslated']]),
                                  'C_V': distribution(p['C_V'] for p in pairs if p['category'] == c and p['pairedTranslated']),
                                  'C_C': distribution(p['C_C'] for p in pairs if p['category'] == c and p['pairedTranslated'])}
                             for c in sorted({p['category'] for p in pairs})},
              'notes': ['Each algorithm/case/scope is attempted once; no MaxSAT solve.',
                        'Ratios use only fully translated pairs; incomplete statuses remain in per-run and pair files.',
                        'Scope is the same expanded formula-size upper bound, even if Alloy atom universes differ.',
                        ('These are all 423 cases omitted by the frozen 200-case campaign.'
                         if data.get('completedPlan') else
                         'This is deterministic stratified sample evidence, not a claim about all 623 cases.')]}
    save(output / 'rq2_same_scope_summary.json', report)
    print(json.dumps(report, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='command', required=True)
    p = subs.add_parser('plan')
    p.add_argument('--output', type=pathlib.Path, required=True)
    p.add_argument('--source', type=pathlib.Path, default=SOURCE)
    p.add_argument('--imports', type=pathlib.Path, default=IMPORTS)
    p.add_argument('--workers', type=int, default=7)
    p.add_argument('--emit-timeout', type=float, default=120)
    p.add_argument('--translate-timeout', type=float, default=180)
    p.add_argument('--heap', default='4g')
    p.add_argument('--java', type=pathlib.Path, default=JAVA)
    p.add_argument('--exclude-plan', type=pathlib.Path,
                   help='Frozen completed 200-case plan; plan only its 423-case complement')
    for name in ('run', 'status', 'summary'):
        subs.add_parser(name).add_argument('directory', type=pathlib.Path)
    args = parser.parse_args()
    if args.command == 'plan': plan(args)
    elif args.command == 'run': run(args)
    elif args.command == 'status': progress(args.directory.resolve())
    else: summarize(args.directory.resolve())


if __name__ == '__main__': main()
