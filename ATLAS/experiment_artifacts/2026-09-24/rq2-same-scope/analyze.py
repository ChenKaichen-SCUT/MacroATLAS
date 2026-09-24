#!/usr/bin/env python3
"""Verify the one-attempt RQ2 same-scope archive and derive paper statistics."""
import collections
import csv
import hashlib
import json
import math
import pathlib
import statistics
import tarfile

ROOT = pathlib.Path(__file__).resolve().parent
ARTIFACTS = ROOT.parent
ATLAS = ROOT.parents[2]
ARCHIVE = ARTIFACTS / 'archives/rq2-same-scope-records-20260924.tar.gz'
MODES = ('atlas-b', 'macro')


def check(value, message):
    if not value:
        raise ValueError(message)


def sha_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def sha(path):
    return sha_bytes(pathlib.Path(path).read_bytes())


def load(path):
    return json.loads(pathlib.Path(path).read_text())


def table(path):
    with pathlib.Path(path).open(newline='') as stream:
        return list(csv.DictReader(stream))


def count_modes(rows, field):
    return {mode: dict(collections.Counter(row[field] for row in rows if row['method'] == mode))
            for mode in MODES}


def distribution(values):
    values = sorted(values)
    return {'n': len(values), 'median': statistics.median(values) if values else None,
            'min': values[0] if values else None, 'max': values[-1] if values else None}


def summarize_group(rows):
    complete = [row for row in rows if row['pairedTranslated'] == 'True']
    return {'cases': len(rows), 'pairedTranslated': len(complete),
            'atlasTranslated': sum(row['atlasStatus'] == 'TRANSLATED_ONLY' for row in rows),
            'macroTranslated': sum(row['macroStatus'] == 'TRANSLATED_ONLY' for row in rows),
            'C_V': distribution(float(row['C_V']) for row in complete),
            'C_C': distribution(float(row['C_C']) for row in complete),
            'macroFewerVars': sum(float(row['C_V']) > 1 for row in complete),
            'macroFewerClauses': sum(float(row['C_C']) > 1 for row in complete)}


def main():
    expected_archive_hash = ARCHIVE.with_name(ARCHIVE.name + '.sha256').read_text().split()[0]
    actual_archive_hash = sha(ARCHIVE)
    check(actual_archive_hash == expected_archive_hash, 'Archive checksum differs')
    plan_path = ROOT / 'plan.json'
    check(sha(plan_path) == (ROOT / 'plan.sha256').read_text().split()[0], 'Plan checksum differs')
    plan, state = load(plan_path), load(ROOT / 'state.json')
    check(state['status'] == 'COMPLETE' and state['completedPairs'] == 200, 'Campaign incomplete')
    check(plan['attemptsPerMethodCaseScope'] == 1 and len(plan['jobs']) == 200 and
          plan['translateTimeoutSec'] == 180 and plan['emitTimeoutSec'] == 120,
          'Run protocol differs')
    check(sha(ATLAS / 'scripts/phase4/rq2_same_scope.py') == plan['collectorSha256'] and
          sha(ATLAS / 'scripts/phase4/Rq2Translate.java') == plan['translatorSourceSha256'] and
          sha(ATLAS / 'lib/AlloyMax-1.0.3.jar') == plan['alloySha256'],
          'Collector/translator/backend differs from frozen plan')
    source_rows = table(ARTIFACTS / 'rq2-encoding/rq2_paper_data.csv')
    check(len(source_rows) == 623 and
          sha(ARTIFACTS / 'rq2-encoding/rq2_paper_data.csv') == plan['sourceSha256'],
          'Original RQ2 source table differs')
    source = {(row['batch'], row['task']): row for row in source_rows}
    check(len(source) == 623, 'Original source has duplicate tasks')
    jobs = plan['jobs']
    check(len({(job['batch'], job['task']) for job in jobs}) == 200 and
          len({job['jobId'] for job in jobs}) == 200 and
          all(job['scope'] in (5, 7, 9, 11, 15) and job['scope'] <= job['B'] and
              job['inputSha256'] == source[job['batch'], job['task']]['inputSha256'] for job in jobs),
          'Selection/input/scope differs')
    runs = table(ROOT / 'summary/rq2_same_scope_per_run.csv')
    pairs = table(ROOT / 'summary/rq2_same_scope_paper_data.csv')
    check(len(runs) == 400 and len(pairs) == 200, 'Wrong summary row counts')
    run_index = {(row['batch'], row['task'], row['method']): row for row in runs}
    pair_index = {(row['batch'], row['task']): row for row in pairs}
    check(len(run_index) == 400 and len(pair_index) == 200, 'Duplicate summary rows')
    check(all(row['attempt'] == '1' and row['solverInvoked'] == 'False' for row in runs),
          'Repeated attempt or solver invocation')
    with tarfile.open(ARCHIVE) as archive:
        # Read gzip sequentially once; random seeking to thousands of members
        # repeatedly decompresses the entire prefix of this archive.
        files = {item.name: archive.extractfile(item).read()
                 for item in archive if item.isfile()}
        names = set(files)
        check(not any(path.endswith('source.bundle') or '/kodkod' in path for path in names),
              'Large solver scratch file included')
        def bytes_at(path):
            name = 'rq2-same-scope-200/' + path
            check(name in files, 'Missing archive file: ' + path)
            return files[name]
        check(sha_bytes(bytes_at('plan.json')) == sha(plan_path) and
              sha_bytes(bytes_at('summary/rq2_same_scope_per_run.csv')) ==
              sha(ROOT / 'summary/rq2_same_scope_per_run.csv') and
              sha_bytes(bytes_at('summary/rq2_same_scope_paper_data.csv')) ==
              sha(ROOT / 'summary/rq2_same_scope_paper_data.csv'),
              'Compact table and archive differ')
        for job in jobs:
            key = job['batch'], job['task']
            pair = pair_index[key]
            check(int(pair['scope']) == job['scope'] and pair['inputSha256'] == job['inputSha256'] and
                  int(pair['B']) == job['B'] and int(pair['b']) == job['b'] and int(pair['K']) == job['K'],
                  'Pair metadata differs from plan')
            input_path = f"inputs/{job['batch']}/{job['jobId']}/input.trace"
            check(sha_bytes(bytes_at(input_path)) == job['inputSha256'], 'Frozen input differs')
            records = {}
            for mode in MODES:
                run = run_index[job['batch'], job['task'], mode]
                prefix = f"jobs/{job['jobId']}/{mode}/"
                started = json.loads(bytes_at(prefix + 'started.json'))
                record = json.loads(bytes_at(prefix + 'record.json'))
                info = json.loads(bytes_at(prefix + 'model-info.json'))
                model = bytes_at(prefix + 'model.als')
                check(started['attempt'] == record['attempt'] == 1 and
                      started['solverInvoked'] is False and record['solverInvoked'] is False and
                      started['scope'] == info['costScope'] == job['scope'] and
                      info['variant'] == mode and info['solverInvoked'] is False and
                      record['modelSha256'] == sha_bytes(model) and
                      record['modelBytes'] == len(model), 'Run artifact provenance differs')
                check(run['status'] == record['status'] and run['modelSha256'] == record['modelSha256'] and
                      run['vars'] == (str(record['vars']) if record['vars'] is not None else '') and
                      run['backendTotalClauses'] ==
                      (str(record['backendTotalClauses']) if record['backendTotalClauses'] is not None else ''),
                      'Per-run table differs from raw record')
                if record['status'] == 'TRANSLATED_ONLY':
                    output = json.loads(bytes_at(prefix + 'translate.stdout'))
                    check(output['status'] == 'TRANSLATED_ONLY' and output['solverInvoked'] is False and
                          all(output[field] == record[field] for field in
                              ('vars', 'primaryVars', 'backendTotalClauses')),
                          'Raw translator output differs')
                records[mode] = record
            a, m = records['atlas-b'], records['macro']
            both = a['status'] == m['status'] == 'TRANSLATED_ONLY'
            check((pair['pairedTranslated'] == 'True') == both and
                  pair['atlasStatus'] == a['status'] and pair['macroStatus'] == m['status'],
                  'Pair status differs')
            for column, numerator, denominator in (
                    ('C_V', a['vars'], m['vars']),
                    ('C_C', a['backendTotalClauses'], m['backendTotalClauses'])):
                if both:
                    check(math.isclose(float(pair[column]), numerator / denominator, rel_tol=1e-12),
                          'Pair ratio differs: ' + column)
                else:
                    check(pair[column] == '', 'Unresolved pair was assigned a ratio')
    existing = load(ROOT / 'summary/rq2_same_scope_summary.json')
    by_scope = {scope: summarize_group([row for row in pairs if int(row['scope']) == scope])
                for scope in (5, 7, 9, 11, 15)}
    categories = sorted({row['category'] for row in pairs})
    by_category = {category: summarize_group([row for row in pairs if row['category'] == category])
                   for category in categories}
    all_group = summarize_group(pairs)
    check(existing['completePairs'] == all_group['pairedTranslated'] == 176 and
          math.isclose(existing['C_V']['median'], all_group['C_V']['median']) and
          math.isclose(existing['C_C']['median'], all_group['C_C']['median']),
          'Server summary differs')
    check(all_group['macroFewerVars'] == 117 and all_group['macroFewerClauses'] == 168,
          'Paired direction counts differ')
    errors = [row for row in runs if row['status'] == 'TRANSLATION_ERROR']
    check(len(errors) == 3 and all('Translation capacity exceeded' in row['error'] for row in errors),
          'Unexpected translation error')
    results = {'sourceCommit': plan['commit'], 'sourceCases': 623,
               'sampleCases': 200, 'methodRuns': 400, 'attemptsPerMethodCaseScope': 1,
               'archiveSha256': actual_archive_hash,
               'planSha256': sha(plan_path),
               'statusByMethod': count_modes(runs, 'status'),
               'statusPairs': [{'atlas': a, 'macro': m, 'cases': n} for (a, m), n in sorted(
                   collections.Counter((r['atlasStatus'], r['macroStatus']) for r in pairs).items())],
               'overall': all_group,
               'byCategory': by_category, 'byScope': by_scope,
               'B_over_K': distribution(float(row['B_over_K']) for row in pairs),
               'KLessThanB': sum(int(row['K']) < int(row['B']) for row in pairs),
               'activeAnchorsOverExpandedSize': distribution(float(row['activeAnchors_over_expandedSize'])
                   for row in pairs if row['activeAnchors_over_expandedSize'] != ''),
               'translationErrorKinds': {'ATLAS_B_CAPACITY_EXCEEDED': len(errors)}}
    (ROOT / 'analysis.json').write_text(json.dumps(results, indent=2, sort_keys=True) + '\n')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
