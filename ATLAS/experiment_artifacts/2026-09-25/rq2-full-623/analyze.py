#!/usr/bin/env python3
"""Independently audit archived RQ2 same-scope records and all-623 statistics."""
import collections
import csv
import hashlib
import io
import json
import math
import pathlib
import statistics
import subprocess
import tarfile

ROOT = pathlib.Path(__file__).resolve().parent
ARTIFACTS = ROOT.parents[1]
ATLAS = ROOT.parents[2]
SOURCE = ARTIFACTS / '2026-09-24/rq2-encoding/rq2_paper_data.csv'
OLD = ARTIFACTS / '2026-09-24/rq2-same-scope'
ARCHIVES = {
    'frozen200': (ARTIFACTS / '2026-09-24/archives/rq2-same-scope-records-20260924.tar.gz',
                  'rq2-same-scope-200', OLD),
    'remaining423': (ARTIFACTS / '2026-09-25/archives/rq2-full-remaining-423-records-20260925.tar.gz',
                     'rq2-same-scope-full-remaining-423', ROOT),
}
MODES = ('atlas-b', 'macro')
SUCCESS = 'TRANSLATED_ONLY'


def check(condition, message):
    if not condition:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def sha(path):
    h = hashlib.sha256()
    with pathlib.Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read_json(path):
    return json.loads(pathlib.Path(path).read_text())


def csv_bytes(raw):
    return list(csv.DictReader(io.StringIO(raw.decode())))


def table(path):
    return csv_bytes(pathlib.Path(path).read_bytes())


def case_key(row):
    return row['batch'], row['task']


def distribution(values):
    values = sorted(values)
    return {'n': len(values), 'median': statistics.median(values) if values else None,
            'min': values[0] if values else None, 'max': values[-1] if values else None}


def group(rows):
    complete = [row for row in rows if row['pairedTranslated'] == 'True']
    return {'cases': len(rows), 'completePairs': len(complete),
            'atlasTranslated': sum(row['atlasStatus'] == SUCCESS for row in rows),
            'macroTranslated': sum(row['macroStatus'] == SUCCESS for row in rows),
            'C_V': distribution(float(row['C_V']) for row in complete),
            'C_C': distribution(float(row['C_C']) for row in complete),
            'macroFewerVars': sum(float(row['C_V']) > 1 for row in complete),
            'macroFewerClauses': sum(float(row['C_C']) > 1 for row in complete)}


def verify_archive(label, source):
    path, prefix, directory = ARCHIVES[label]
    expected_hash = pathlib.Path(str(path) + '.sha256').read_text().split()[0]
    archive_hash = sha(path)
    check(archive_hash == expected_hash, label + ': archive SHA-256 differs')
    plan = read_json(directory / 'plan.json')
    check(sha(directory / 'plan.json') == (directory / 'plan.sha256').read_text().split()[0],
          label + ': plan checksum differs')
    state = read_json(directory / 'state.json')
    expected_count = 200 if label == 'frozen200' else 423
    check(state['status'] == 'COMPLETE' and state['completedPairs'] == expected_count and
          len(plan['jobs']) == expected_count and plan['attemptsPerMethodCaseScope'] == 1,
          label + ': plan or state incomplete')
    check(plan['sourceSha256'] == sha(SOURCE), label + ': source table differs')
    collector = subprocess.check_output(['git', 'show',
        plan['commit'] + ':ATLAS/scripts/phase4/rq2_same_scope.py'], cwd=ATLAS.parent)
    translator = subprocess.check_output(['git', 'show',
        plan['commit'] + ':ATLAS/scripts/phase4/Rq2Translate.java'], cwd=ATLAS.parent)
    check(digest(collector) == plan['collectorSha256'] and
          digest(translator) == plan['translatorSourceSha256'] and
          sha(ATLAS / 'lib/AlloyMax-1.0.3.jar') == plan['alloySha256'],
          label + ': frozen code/backend SHA-256 differs')
    check(len({case_key(job) for job in plan['jobs']}) == expected_count and
          all(case_key(job) in source and job['inputSha256'] == source[case_key(job)]['inputSha256']
              and 1 <= job['scope'] <= job['B'] for job in plan['jobs']),
          label + ': duplicate case, input, or scope mismatch')
    if label == 'remaining423':
        check(plan['completedPlan']['sha256'] == sha(OLD / 'plan.json'),
              'New plan does not reference frozen 200-case plan')
    with tarfile.open(path) as archive:
        files = {member.name: archive.extractfile(member).read()
                 for member in archive if member.isfile()}
    check(not any(name.endswith('.wcnf') or '/kodkod' in name for name in files),
          label + ': scratch CNF/Kodkod files unexpectedly archived')

    def raw(relative):
        name = prefix + '/' + relative
        check(name in files, label + ': missing ' + relative)
        return files[name]

    check(digest(raw('plan.json')) == sha(directory / 'plan.json') and
          digest(raw('state.json')) == sha(directory / 'state.json'),
          label + ': local metadata differs from raw archive')
    runs_path = directory / 'summary/rq2_same_scope_per_run.csv'
    pairs_path = directory / 'summary/rq2_same_scope_paper_data.csv'
    check(digest(raw('summary/rq2_same_scope_per_run.csv')) == sha(runs_path) and
          digest(raw('summary/rq2_same_scope_paper_data.csv')) == sha(pairs_path),
          label + ': local tables differ from raw archive')
    runs = table(runs_path)
    pairs = table(pairs_path)
    check(len(runs) == expected_count * 2 and len(pairs) == expected_count,
          label + ': wrong table sizes')
    indexed_runs = {(row['batch'], row['task'], row['method']): row for row in runs}
    indexed_pairs = {case_key(row): row for row in pairs}
    check(len(indexed_runs) == len(runs) and len(indexed_pairs) == len(pairs),
          label + ': duplicate table keys')
    for job in plan['jobs']:
        key = case_key(job)
        pair = indexed_pairs[key]
        check(int(pair['scope']) == job['scope'] and pair['inputSha256'] == job['inputSha256'] and
              int(pair['B']) == job['B'] and int(pair['b']) == job['b'] and
              int(pair['K']) == job['K'], label + ': case metadata differs')
        trace = raw(f"inputs/{job['batch']}/{job['jobId']}/input.trace")
        check(digest(trace) == job['inputSha256'], label + ': archived input differs')
        result = {}
        for mode in MODES:
            stem = f"jobs/{job['jobId']}/{mode}/"
            marker = json.loads(raw(stem + 'started.json'))
            record = json.loads(raw(stem + 'record.json'))
            info = json.loads(raw(stem + 'model-info.json'))
            model = raw(stem + 'model.als')
            run = indexed_runs[key + (mode,)]
            check(marker['attempt'] == record['attempt'] == 1 and
                  marker['solverInvoked'] is False and record['solverInvoked'] is False and
                  marker['scope'] == info['costScope'] == job['scope'] and
                  info['variant'] == mode and info['solverInvoked'] is False and
                  record['modelSha256'] == digest(model) and record['modelBytes'] == len(model),
                  label + ': raw attempt/model provenance differs')
            check(run['attempt'] == '1' and run['solverInvoked'] == 'False' and
                  run['status'] == record['status'] and run['modelSha256'] == record['modelSha256'],
                  label + ': per-run status/model differs')
            for field in ('vars', 'primaryVars', 'backendTotalClauses'):
                check(run[field] == (str(record[field]) if record[field] is not None else ''),
                      label + ': per-run backend count differs')
            if record['status'] == SUCCESS:
                callback = json.loads(raw(stem + 'translate.stdout'))
                check(callback['solverInvoked'] is False and callback['status'] == SUCCESS and
                      all(callback[field] == record[field] for field in
                          ('vars', 'primaryVars', 'backendTotalClauses')),
                      label + ': translator callback differs')
            result[mode] = record
        a, m = result['atlas-b'], result['macro']
        complete = a['status'] == m['status'] == SUCCESS
        check((pair['pairedTranslated'] == 'True') == complete and
              pair['atlasStatus'] == a['status'] and pair['macroStatus'] == m['status'],
              label + ': paired status differs')
        for column, numerator, denominator in (('C_V', a['vars'], m['vars']),
                                                 ('C_C', a['backendTotalClauses'],
                                                  m['backendTotalClauses'])):
            if complete:
                check(math.isclose(float(pair[column]), numerator / denominator, rel_tol=1e-12),
                      label + ': paired ratio differs')
            else:
                check(pair[column] == '', label + ': failed pair has a ratio')
    return {'plan': plan, 'runs': runs, 'pairs': pairs, 'archiveSha256': archive_hash,
            'planSha256': sha(directory / 'plan.json')}


def main():
    source_rows = table(SOURCE)
    source = {case_key(row): row for row in source_rows}
    check(len(source_rows) == len(source) == 623, 'Source table is not 623 unique cases')
    old = verify_archive('frozen200', source)
    new = verify_archive('remaining423', source)
    campaigns = {'frozen200': old, 'remaining423': new}
    all_runs = {(row['batch'], row['task'], row['method']): {'campaign': label, **row}
                for label, data in campaigns.items() for row in data['runs']}
    all_pairs = {case_key(row): {'campaign': label, **row}
                 for label, data in campaigns.items() for row in data['pairs']}
    check(len(all_runs) == 1246 and len(all_pairs) == 623 and set(all_pairs) == set(source),
          'Campaign overlap or incomplete source coverage')
    runs = table(ROOT / 'summary/rq2_full_623_per_run.csv')
    pairs = table(ROOT / 'summary/rq2_full_623_paper_data.csv')
    check(len(runs) == 1246 and len(pairs) == 623 and
          all_runs == {(row['batch'], row['task'], row['method']): row for row in runs} and
          all_pairs == {case_key(row): row for row in pairs},
          'Combined tables differ from archived campaign tables')
    server = read_json(ROOT / 'summary/rq2_full_623_summary.json')
    overall = group(pairs)
    statuses = {mode: dict(collections.Counter(row['status'] for row in runs if row['method'] == mode))
                for mode in MODES}
    by_constraint = {name: group([row for row in pairs if
                     (int(row['qStates']) == 1) == (name == '无约束 q=1')])
                     for name in ('无约束 q=1', '受约束 q>1')}
    by_family = {name: group([row for row in pairs if row['family'] == name])
                 for name in sorted({row['family'] for row in pairs})}
    by_scope = {str(scope): group([row for row in pairs if int(row['scope']) == scope])
                for scope in sorted({int(row['scope']) for row in pairs})}
    by_budget = {str(b): group([row for row in pairs if int(row['b']) == b])
                 for b in sorted({int(row['b']) for row in pairs})}
    status_pairs = [{'atlas': a, 'macro': m, 'cases': n} for (a, m), n in sorted(
                    collections.Counter((row['atlasStatus'], row['macroStatus'])
                                        for row in pairs).items())]
    expected = {'overall': overall, 'statuses': statuses, 'byConstraint': by_constraint,
                'byFamily': by_family, 'byScope': by_scope, 'byBinaryBudget': by_budget,
                'statusPairs': status_pairs, 'B_over_K': distribution(float(row['B_over_K'])
                                                                     for row in pairs),
                'KLessThanB': sum(int(row['K']) < int(row['B']) for row in pairs)}
    for field, value in expected.items():
        check(server[field] == value, 'Server summary differs: ' + field)
    check(server['provenance']['oldPlanSha256'] == old['planSha256'] and
          server['provenance']['newPlanSha256'] == new['planSha256'] and
          server['provenance']['sourceSha256'] == sha(SOURCE),
          'Server summary provenance differs')
    analysis = {'sourceCases': 623, 'methodRuns': 1246, 'singleAttempt': True,
                'solverInvoked': False, 'overall': overall, 'statuses': statuses,
                'statusPairs': status_pairs, 'byConstraint': by_constraint,
                'byFamily': by_family, 'byScope': by_scope, 'byBinaryBudget': by_budget,
                'byCampaign': {label: group([row for row in pairs if row['campaign'] == label])
                               for label in campaigns},
                'B_over_K': expected['B_over_K'], 'KLessThanB': expected['KLessThanB'],
                'archivesSha256': {label: data['archiveSha256'] for label, data in campaigns.items()},
                'plansSha256': {label: data['planSha256'] for label, data in campaigns.items()},
                'fullPaperDataSha256': sha(ROOT / 'summary/rq2_full_623_paper_data.csv'),
                'fullPerRunSha256': sha(ROOT / 'summary/rq2_full_623_per_run.csv'),
                'serverSummarySha256': sha(ROOT / 'summary/rq2_full_623_summary.json')}
    (ROOT / 'analysis.json').write_text(json.dumps(analysis, ensure_ascii=False,
                                                  indent=2, sort_keys=True) + '\n')
    print('PASS: 623 unique cases, 1246 one-attempt records, source/model/CNF hashes and all statistics')
    print(json.dumps({'completePairs': overall['completePairs'],
                      'medianC_V': overall['C_V']['median'],
                      'medianC_C': overall['C_C']['median'],
                      'statuses': statuses}, indent=2))


if __name__ == '__main__':
    main()
