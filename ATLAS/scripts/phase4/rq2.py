#!/usr/bin/env python3
"""RQ2: reuse frozen E4 metrics and translate only missing CNFs, once per job."""
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

from isolation import allocate, topology
from validate_results import validate

ATLAS = pathlib.Path(__file__).resolve().parents[2]
ROOT = pathlib.Path('/srv/macroatlas/imports')
JAVA = pathlib.Path('/srv/macroatlas/jdks/jdk8u462-b08/bin/java')
JAVAC = JAVA.with_name('javac')
PYTHON = pathlib.Path('/srv/macroatlas/venv/bin/python')
JAR = ATLAS / 'lib/AlloyMax-1.0.3.jar'
MODES = ('atlas-b', 'macro')
METRICS = ('primaryVars', 'vars', 'backendTotalClauses')


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha256(path):
    h = hashlib.sha256()
    with pathlib.Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(pathlib.Path(path).read_text())


def save(path, value):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    tmp.replace(path)


def git_commit():
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ATLAS, text=True).strip()
    dirty = subprocess.check_output(['git', 'status', '--porcelain'], cwd=ATLAS, text=True).strip()
    if dirty:
        raise ValueError('Commit the RQ2 collector before creating a formal plan')
    return commit


def rows_from(path):
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream))


def trace_stats(text):
    blocks = text.split('\n---\n')
    if len(blocks) < 2:
        raise ValueError('Bad frozen .trace format')
    positive = [s for s in blocks[0].splitlines() if s.strip()]
    negative = [s for s in blocks[1].splitlines() if s.strip()]
    traces = positive + negative
    if not traces:
        raise ValueError('No traces')
    lengths = [len(x.split('::')[0].split(';')) for x in traces]
    ap = len(traces[0].split('::')[0].split(';')[0].split(','))
    return dict(numAP=ap, positiveTraces=len(positive), negativeTraces=len(negative),
                minTraceLength=min(lengths), maxTraceLength=max(lengths),
                meanTraceLength=sum(lengths) / len(lengths))


def campaign_jobs(directory, batch, expected):
    if read(directory / 'state.json')['status'] != 'COMPLETE':
        raise ValueError('E4 source campaign incomplete: ' + str(directory))
    plan = read(directory / 'plan.json')
    phase = plan['phases'][0]
    if len(plan['phases']) != 1 or phase['id'] != 'e4-matched' or phase['variants'] != list(MODES) or phase['repeats'] != 1:
        raise ValueError('Unexpected E4 source protocol')
    if len(phase['tasks']) != expected or plan['b'] != int(batch[1:]):
        raise ValueError('Wrong task count/b')
    rows, _ = validate(directory / 'e4-matched/merged')
    if len(rows) != expected * 2:
        raise ValueError('Wrong row count')
    raw = {(row['task'], row['variant']): row for row in rows}
    commands = {}
    for command_file in (directory / 'e4-matched/workers').glob('w*/*/command.json'):
        command = read(command_file)
        key = command['task'], command['variant']
        if key in commands:
            raise ValueError('Duplicate E4 command')
        commands[key] = (command_file.parent, command)
    if set(raw) != set(commands):
        raise ValueError('Missing E4 artifacts')
    coverage = {}
    for file in (directory / 'e4-matched/inputs').glob('w*/coverage.csv'):
        for row in rows_from(file):
            coverage[row['task']] = row['recognizedFeatures']
    task_hashes = {entry['task']: entry['sha256'] for entry in phase['tasks']}
    inputs = {}
    with tarfile.open(directory / 'inputs.tar.gz') as archive:
        for task, expected_hash in task_hashes.items():
            content = archive.extractfile('e4-matched/' + task).read()
            if hashlib.sha256(content).hexdigest() != expected_hash:
                raise ValueError('Frozen input hash mismatch: ' + task)
            inputs[task] = trace_stats(content.decode())
    jobs = []
    for task in sorted(task_hashes):
        for mode in MODES:
            folder, command = commands[task, mode]
            row = raw[task, mode]
            if command['sha256'] != task_hashes[task] or command['repeat'] != 1 or row['repeat'] != '1':
                raise ValueError('Source command identity changed')
            if int(row['K']) != min(int(row['B']), int(row['p']) + 3 * int(row['b']) + 2):
                raise ValueError('K bound mismatch')
            seen = set()
            models = []
            for file in sorted(folder.glob('*.als')):
                digest = sha256(file)
                if digest in seen:
                    continue
                seen.add(digest)
                models.append(dict(path=str(file), sha256=digest, bytes=file.stat().st_size, name=file.name))
            if not models:
                raise ValueError('No frozen model: ' + task + ' ' + mode)
            stage = read(folder / 'stage.json') if (folder / 'stage.json').is_file() else {}
            macro_info = {}
            if mode == 'macro':
                state_file = folder / 'constraint_states.txt'
                catalog_file = folder / 'fiber_catalog.txt'
                q = len(state_file.read_text().splitlines())
                fibers = len(catalog_file.read_text().splitlines())
                if q < 1 or fibers != stage.get('fiberCount'):
                    raise ValueError('Macro catalog/state mismatch: ' + task)
                macro_info = dict(qStates=q, fiberCatalogSize=fibers,
                    unquotientedFiberCount=stage.get('unquotientedFiberCount'),
                    encodedFiberCount=stage.get('encodedFiberCount'),
                    costScope=stage.get('costScope'),
                    reducedTraceCount=stage.get('reducedTraceCount'))
            source = 'E4_REUSED' if all(row.get(field) not in ('', None) for field in METRICS) else 'TRANSLATE_ONLY'
            name = hashlib.sha256((batch + '\0' + task + '\0' + mode).encode()).hexdigest()[:16] + '-' + mode
            jobs.append(dict(batch=batch, task=task, variant=mode, family=row['family'],
                inputSha256=task_hashes[task], trace=inputs[task], features=coverage.get(task, ''),
                row=row, models=models, macroInfo=macro_info, metricSource=source,
                jobId=name, sourceFolder=str(folder)))
    source = dict(campaign=str(directory), sourceCommit=plan['environment']['commit'],
        planSha256=sha256(directory / 'plan.json'), rawSha256=sha256(directory / 'e4-matched/merged/raw.csv'),
        inputsSha256=sha256(directory / 'inputs.tar.gz'), cases=expected, b=plan['b'])
    return jobs, source


def plan(args):
    output = args.output.resolve()
    if output.exists():
        raise ValueError('RQ2 output must be new')
    if args.workers < 1 or args.timeout <= 0:
        raise ValueError('Invalid worker/timeout setting')
    commit = git_commit()
    jobs = []
    sources = {}
    for batch, directory, expected in (('b2', args.b2.resolve(), 584), ('b3', args.b3.resolve(), 39)):
        block, source = campaign_jobs(directory, batch, expected)
        jobs += block
        sources[batch] = source
    if len(jobs) != 1246 or len({(j['batch'], j['task'], j['variant']) for j in jobs}) != 1246:
        raise ValueError('Expected exactly 1246 distinct RQ2 jobs')
    cpus, reserved = allocate(topology(), args.workers)
    output.mkdir(parents=True)
    classes = output / 'classes'
    classes.mkdir()
    subprocess.run([str(JAVAC), '-cp', str(JAR), '-d', str(classes), str(ATLAS / 'scripts/phase4/Rq2Translate.java')], check=True)
    class_hashes = {file.name: sha256(file) for file in sorted(classes.glob('*.class'))}
    data = dict(schemaVersion=1, createdUtc=utc(), commit=commit, source=sources,
        java=str(args.java.resolve()), javaHeap=args.heap, translatorClassSha256=class_hashes,
        translatorSourceSha256=sha256(ATLAS / 'scripts/phase4/Rq2Translate.java'),
        collectorSha256=sha256(pathlib.Path(__file__)), jarSha256=sha256(JAR),
        timeoutSec=args.timeout, workers=args.workers, workerCpus=cpus, reservedCpus=reserved,
        attemptsPerMissingMetricJob=1, jobs=jobs)
    save(output / 'plan.json', data)
    (output / 'plan.sha256').write_text(sha256(output / 'plan.json') + '  plan.json\n')
    save(output / 'state.json', dict(status='READY', updatedUtc=utc()))
    (output / 'logs').mkdir()
    (output / 'logs/controller.log').touch()
    subprocess.run(['git', 'bundle', 'create', str(output / 'source.bundle'), 'HEAD'], cwd=ATLAS, check=True)
    print(f'Planned {len(jobs)//2} paired cases, {len(jobs)} RQ2 records; '
          f'{sum(j["metricSource"] == "TRANSLATE_ONLY" for j in jobs)} translation-only jobs')
    print('Worker CPUs:', cpus, 'reserved:', reserved)
    print(output)


def load_plan(directory):
    directory = directory.resolve()
    if sha256(directory / 'plan.json') != (directory / 'plan.sha256').read_text().split()[0]:
        raise ValueError('RQ2 plan checksum changed')
    data = read(directory / 'plan.json')
    if git_commit() != data['commit']:
        raise ValueError('RQ2 code changed after planning')
    if {file.name: sha256(file) for file in sorted((directory / 'classes').glob('*.class'))} != data['translatorClassSha256']:
        raise ValueError('RQ2 translator class changed')
    if sha256(JAR) != data['jarSha256']:
        raise ValueError('AlloyMax binary changed')
    if len(data['jobs']) != 1246 or data['attemptsPerMissingMetricJob'] != 1:
        raise ValueError('RQ2 job protocol changed')
    for batch in ('b2', 'b3'):
        source = data['source'][batch]
        d = pathlib.Path(source['campaign'])
        for name, saved, path in (
            ('plan', source['planSha256'], d / 'plan.json'),
            ('raw', source['rawSha256'], d / 'e4-matched/merged/raw.csv'),
            ('inputs', source['inputsSha256'], d / 'inputs.tar.gz')):
            if sha256(path) != saved:
                raise ValueError(batch + ' source ' + name + ' changed')
    return data


def record_path(directory, job):
    return directory / 'jobs' / job['batch'] / job['jobId'] / 'record.json'


def do_job(directory, data, job, cpu):
    folder = record_path(directory, job).parent
    final = folder / 'record.json'
    if final.is_file():
        return read(final)
    if folder.exists():
        record = dict(status='INTERRUPTED_UNRECORDED', metricSource=job['metricSource'],
            attempt=1 if job['metricSource'] == 'TRANSLATE_ONLY' else 0,
            error='RQ2 job directory exists but no final record exists; no automatic rerun')
        save(final, record)
        return record
    folder.mkdir(parents=True)
    row = job['row']
    if job['metricSource'] == 'E4_REUSED':
        record = dict(status='REUSED_E4', metricSource='E4_REUSED', attempt=0,
            primaryVars=int(row['primaryVars']), vars=int(row['vars']),
            backendTotalClauses=int(row['backendTotalClauses']), modelMetrics=[],
            error='', wallSec=0)
        save(final, record)
        return record
    save(folder / 'started.json', dict(startedUtc=utc(), attempt=1, modelSha256=[x['sha256'] for x in job['models']],
        sourceCommit=data['commit'], solverInvoked=False))
    started = time.monotonic()
    models = []
    error = ''
    status = 'TRANSLATED_ONLY'
    for index, model in enumerate(job['models']):
        path = pathlib.Path(model['path'])
        if sha256(path) != model['sha256']:
            status = 'SOURCE_CHANGED'
            error = 'Frozen .als hash changed: ' + model['name']
            break
        remaining = data['timeoutSec'] - (time.monotonic() - started)
        if remaining <= 0:
            status = 'TIMEOUT'
            error = 'RQ2 per-job translation time budget exhausted'
            break
        scratch = folder / ('tmp-%02d' % index)
        scratch.mkdir()
        command = ['taskset', '-c', cpu, data['java'], '-XX:ActiveProcessorCount=2',
            '-Xms256m', '-Xmx' + data['javaHeap'], '-Djava.library.path=' + str(ATLAS / 'lib'),
            '-Djava.io.tmpdir=' + str(scratch), '-cp', str(directory / 'classes') + ':' + str(JAR),
            'Rq2Translate', str(path)]
        with (folder / ('model-%02d.stdout' % index)).open('w') as out, (folder / ('model-%02d.stderr' % index)).open('w') as err:
            process = subprocess.Popen(command, cwd=ATLAS, stdout=out, stderr=err, start_new_session=True)
            try:
                exit_code = process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                status = 'TIMEOUT'
                error = 'CNF translation timed out: ' + model['name']
                break
        if exit_code != 0:
            status = 'TRANSLATION_ERROR'
            error = (folder / ('model-%02d.stderr' % index)).read_text(errors='replace')[-2000:]
            break
        output = (folder / ('model-%02d.stdout' % index)).read_text()
        try:
            metric = json.loads(output.strip())
            assert metric['status'] == 'TRANSLATED_ONLY' and metric['solverInvoked'] is False
        except (ValueError, KeyError, AssertionError) as exc:
            status = 'TRANSLATION_ERROR'
            error = 'Unexpected translator output: ' + str(exc)
            break
        models.append(dict(name=model['name'], sha256=model['sha256'], **metric))
        scratch.rmdir() if not any(scratch.iterdir()) else None
    record = dict(status=status, metricSource='TRANSLATE_ONLY', attempt=1,
        primaryVars=max((m['primaryVars'] for m in models), default=None) if status == 'TRANSLATED_ONLY' else None,
        vars=max((m['vars'] for m in models), default=None) if status == 'TRANSLATED_ONLY' else None,
        backendTotalClauses=max((m['backendTotalClauses'] for m in models), default=None) if status == 'TRANSLATED_ONLY' else None,
        modelMetrics=models, translatedModels=len(models), expectedModels=len(job['models']),
        error=error, wallSec=time.monotonic() - started)
    save(final, record)
    print(utc(), job['batch'], job['task'], job['variant'], status,
          str(record['vars'] or ''), str(record['backendTotalClauses'] or ''), flush=True)
    return record


def status(directory):
    directory = directory.resolve()
    data = read(directory / 'plan.json')
    counts = collections.Counter()
    statuses = collections.defaultdict(collections.Counter)
    grouped = collections.defaultdict(set)
    for job in data['jobs']:
        file = record_path(directory, job)
        if file.is_file():
            record = read(file)
            counts[job['variant']] += 1
            statuses[job['variant']][record['status']] += 1
            grouped[(job['batch'], job['task'])].add(job['variant'])
    complete = sum(group == set(MODES) for group in grouped.values())
    state = read(directory / 'state.json')['status']
    print(f'RQ2 cases {complete}/623 | ATLAS-B {counts["atlas-b"]}/623 | MacroATLAS {counts["macro"]}/623 | state={state}')
    for method in MODES:
        print(method, dict(statuses[method]))
    return complete


def run(args):
    directory = args.directory.resolve()
    lock = (directory / 'controller.lock').open('w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise ValueError('RQ2 controller already running')
    data = load_plan(directory)
    if read(directory / 'state.json')['status'] == 'COMPLETE':
        status(directory)
        return
    save(directory / 'state.json', dict(status='RUNNING', updatedUtc=utc()))
    def worker(index):
        for offset, job in enumerate(data['jobs']):
            if offset % data['workers'] == index:
                do_job(directory, data, job, data['workerCpus'][index])
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=data['workers']) as pool:
            futures = [pool.submit(worker, i) for i in range(data['workers'])]
            for future in concurrent.futures.as_completed(futures):
                future.result()
        completed = status(directory)
        state = 'COMPLETE' if completed == 623 else 'FAILED'
        save(directory / 'state.json', dict(status=state, completedCases=completed, updatedUtc=utc()))
        if state != 'COMPLETE':
            raise RuntimeError('RQ2 incomplete; started jobs will not be relaunched automatically')
        summarize(directory)
    except BaseException as exc:
        save(directory / 'state.json', dict(status='FAILED', error=str(exc), updatedUtc=utc()))
        raise
    finally:
        lock.close()


def dist(values):
    xs = sorted(x for x in values if x is not None and math.isfinite(x))
    if not xs:
        return dict(count=0, min=None, p25=None, median=None, p75=None, max=None)
    def quantile(q):
        offset = (len(xs) - 1) * q
        low = int(offset)
        high = min(low + 1, len(xs) - 1)
        return xs[low] + (xs[high] - xs[low]) * (offset - low)
    return dict(count=len(xs), min=xs[0], p25=quantile(.25), median=quantile(.5), p75=quantile(.75), max=xs[-1])


def write_csv(path, rows):
    if not rows:
        return
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def summarize(directory):
    data = load_plan(directory)
    if sum(record_path(directory, job).is_file() for job in data['jobs']) != 1246:
        raise ValueError('RQ2 summary requires all 1246 one-attempt records')
    runs = []
    pairs = collections.defaultdict(dict)
    status_counts = collections.Counter()
    for job in data['jobs']:
        record = read(record_path(directory, job))
        row = job['row']
        macro = job['macroInfo']
        result = dict(batch=job['batch'], task=job['task'], family=job['family'], method=job['variant'],
            inputSha256=job['inputSha256'], sourceCommit=data['source'][job['batch']]['sourceCommit'],
            B=int(row['B']), b=int(row['b']), p=int(row['p']), K=int(row['K']),
            numAP=job['trace']['numAP'], positiveTraces=job['trace']['positiveTraces'],
            negativeTraces=job['trace']['negativeTraces'], minTraceLength=job['trace']['minTraceLength'],
            maxTraceLength=job['trace']['maxTraceLength'], meanTraceLength=job['trace']['meanTraceLength'],
            constraintFeatures=job['features'], objectiveKind=row['objectiveKind'],
            e4Status=row['status'], e4WallSec=row['totalSec'], e4Verification=row['verification'],
            metricStatus=record['status'], metricSource=record['metricSource'], rq2Attempts=record['attempt'],
            primaryVars=record.get('primaryVars'), vars=record.get('vars'),
            backendTotalClauses=record.get('backendTotalClauses'), hardClauses='', softClauses='',
            modelBytes=max(m['bytes'] for m in job['models']), modelCount=len(job['models']),
            modelSha256=';'.join(m['sha256'] for m in job['models']),
            qStates=macro.get('qStates', ''), fiberCatalogSize=macro.get('fiberCatalogSize', ''),
            unquotientedFiberCount=macro.get('unquotientedFiberCount', ''),
            encodedFiberCount=macro.get('encodedFiberCount', ''), costScope=macro.get('costScope', row.get('costScope', '')),
            selectedFiberCount=row.get('selectedFiberCount', '') if row['status']=='SAT' else '',
            meanRepresentativeLength=row.get('meanRepresentativeLength', '') if row['status']=='SAT' else '',
            maxRepresentativeLength=row.get('maxRepresentativeLength', '') if row['status']=='SAT' else '',
            activeAnchors=row.get('activeAnchors', '') if row['status']=='SAT' else '',
            activeMacroEdges=row.get('activeMacroEdges', '') if row['status']=='SAT' else '',
            error=record.get('error', ''), translationWallSec=record.get('wallSec', ''))
        runs.append(result)
        key = job['batch'], job['task']
        if job['variant'] in pairs[key]:
            raise ValueError('Duplicate case/method in summary')
        pairs[key][job['variant']] = result
        status_counts[(job['variant'],record['status'])] += 1
    paper = []
    for (batch, task), pair in sorted(pairs.items()):
        if set(pair) != set(MODES):
            raise ValueError('Unpaired RQ2 task')
        old, macro = (pair[m] for m in MODES)
        if any(old[k] != macro[k] for k in ('B','b','p','K','inputSha256','objectiveKind')):
            raise ValueError('Matched domain differs')
        def ratio(a, b):
            return a / b if a is not None and b is not None and b > 0 else ''
        paper.append(dict(batch=batch, task=task, family=old['family'], inputSha256=old['inputSha256'],
            B=old['B'], b=old['b'], p=old['p'], K=old['K'], C_K=old['B']/old['K'],
            numAP=old['numAP'], positiveTraces=old['positiveTraces'], negativeTraces=old['negativeTraces'],
            minTraceLength=old['minTraceLength'], maxTraceLength=old['maxTraceLength'],
            meanTraceLength=old['meanTraceLength'], constraintFeatures=old['constraintFeatures'],
            objectiveKind=old['objectiveKind'], isRepair=old['objectiveKind']=='REPAIR',
            qStates=macro['qStates'], fiberCatalogSize=macro['fiberCatalogSize'],
            unquotientedFiberCount=macro['unquotientedFiberCount'], encodedFiberCount=macro['encodedFiberCount'],
            selectedFiberCount=macro['selectedFiberCount'], meanRepresentativeLength=macro['meanRepresentativeLength'],
            maxRepresentativeLength=macro['maxRepresentativeLength'], activeAnchors=macro['activeAnchors'],
            activeMacroEdges=macro['activeMacroEdges'],
            atlasPrimaryVars=old['primaryVars'], macroPrimaryVars=macro['primaryVars'],
            atlasVars=old['vars'], macroVars=macro['vars'], C_V=ratio(old['vars'], macro['vars']),
            atlasTotalClauses=old['backendTotalClauses'], macroTotalClauses=macro['backendTotalClauses'],
            C_C=ratio(old['backendTotalClauses'], macro['backendTotalClauses']),
            atlasHardClauses='', atlasSoftClauses='', macroHardClauses='', macroSoftClauses='',
            atlasModelBytes=old['modelBytes'], macroModelBytes=macro['modelBytes'],
            C_ModelBytes=ratio(old['modelBytes'], macro['modelBytes']),
            atlasModelCount=old['modelCount'], macroModelCount=macro['modelCount'],
            atlasMetricStatus=old['metricStatus'], macroMetricStatus=macro['metricStatus'],
            atlasMetricSource=old['metricSource'], macroMetricSource=macro['metricSource'],
            atlasRq2Attempts=old['rq2Attempts'], macroRq2Attempts=macro['rq2Attempts'],
            atlasE4Status=old['e4Status'], macroE4Status=macro['e4Status'],
            atlasE4WallSec=old['e4WallSec'], macroE4WallSec=macro['e4WallSec'],
            atlasModelSha256=old['modelSha256'], macroModelSha256=macro['modelSha256']))
    output = directory / 'summary'
    output.mkdir(exist_ok=True)
    write_csv(output / 'rq2_per_run.csv', runs)
    write_csv(output / 'rq2_paper_data.csv', paper)
    report = dict(cases=623, methodRuns=1246, pairedVarClauses=sum(bool(r['C_V']) and bool(r['C_C']) for r in paper),
        metricStatuses={m:dict(collections.Counter({status:count for (method,status),count in status_counts.items() if method==m})) for m in MODES},
        metricSource={m:dict(collections.Counter(r['metricSource'] for r in runs if r['method']==m)) for m in MODES},
        distributions={key:dist(float(r[key]) if r[key] != '' else None for r in paper)
            for key in ('C_K','C_V','C_C','C_ModelBytes','fiberCatalogSize','selectedFiberCount')},
        byBatch={batch:{key:dist(float(r[key]) if r[key] != '' else None for r in paper if r['batch']==batch)
            for key in ('C_K','C_V','C_C','C_ModelBytes')} for batch in ('b2','b3')},
        notes=['CNF translation callback stops before SAT solve; no E4 learning was rerun.',
               'AlloyMax reporter exposes total variables/clauses, not reliable hard/soft splits.',
               'Selected fibers and active structures require SAT assignments; blank for timeout/UNSAT.',
               'C_V and C_C use the maximum backend counts across attempted models for each method.',
               'Ratios omit pairs with unavailable CNF metrics; coverage is reported explicitly.'])
    save(output / 'rq2_summary.json', report)
    print(json.dumps(report, indent=2))


def install(args):
    directory = args.directory.resolve()
    load_plan(directory)
    unit = pathlib.Path('/etc/systemd/system/macroatlas-rq2.service')
    content = '\n'.join(['[Unit]', 'Description=MacroATLAS RQ2 encoding-only collection', 'After=network.target', '',
        '[Service]', 'Type=simple', 'WorkingDirectory='+str(ATLAS),
        'ExecStart='+str(PYTHON)+' '+str(pathlib.Path(__file__).resolve())+' run '+str(directory),
        'Environment=PYTHONUNBUFFERED=1', 'Restart=no', 'KillMode=control-group', 'TimeoutStopSec=15',
        'StandardOutput=append:'+str(directory/'logs/controller.log'),
        'StandardError=append:'+str(directory/'logs/controller.log'), '', '[Install]', 'WantedBy=multi-user.target', ''])
    if unit.exists() and unit.read_text() != content:
        raise ValueError('Different RQ2 service already installed')
    unit.write_text(content)
    subprocess.run(['systemctl','daemon-reload'],check=True)
    print('Installed, not started:',unit)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command',required=True)
    p = commands.add_parser('plan')
    p.add_argument('--b2',type=pathlib.Path,default=ROOT/'full-e4-b2')
    p.add_argument('--b3',type=pathlib.Path,default=ROOT/'full-e4-b3')
    p.add_argument('--output',type=pathlib.Path,required=True)
    p.add_argument('--workers',type=int,default=7)
    p.add_argument('--timeout',type=float,default=180)
    p.add_argument('--heap',default='4g')
    p.add_argument('--java',type=pathlib.Path,default=JAVA)
    for name in ('run','status','summary','install-service'):
        sub = commands.add_parser(name)
        sub.add_argument('directory',type=pathlib.Path)
    args = parser.parse_args()
    if args.command=='plan':plan(args)
    elif args.command=='run':run(args)
    elif args.command=='status':status(args.directory)
    elif args.command=='summary':summarize(args.directory)
    else:install(args)


if __name__=='__main__':main()
