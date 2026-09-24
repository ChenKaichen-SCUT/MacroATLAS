#!/usr/bin/env python3
"""Independently verify and summarize the archived certified RQ4 campaign."""
import collections
import csv
import hashlib
import json
import math
import pathlib
import statistics
import tarfile

ROOT = pathlib.Path(__file__).resolve().parent
METHODS = ('ATLAS-B', 'MacroATLAS')


def rows(relative):
    with (ROOT / relative).open(newline='') as stream:
        return list(csv.DictReader(stream))


def data(relative):
    return json.loads((ROOT / relative).read_text())


def sha(relative):
    return hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()


def check(condition, message):
    if not condition:
        raise ValueError(message)


def summarize_axis(rows_in, axis):
    subset = [row for row in rows_in if row['axis'] == axis]
    cases = collections.defaultdict(dict)
    for row in subset:
        check(row['algorithm'] in METHODS and row['repeat'] == '1', 'Invalid method/repeat')
        check(row['algorithm'] not in cases[row['task']], 'Duplicate algorithm/task')
        cases[row['task']][row['algorithm']] = row
    check(all(set(pair) == set(METHODS) for pair in cases.values()), 'Unpaired A/B case')
    by_method = {}
    for method in METHODS:
        part = [pair[method] for pair in cases.values()]
        solved = [row for row in part if row['status'] == 'SAT']
        by_method[method] = {
            'SAT': len(solved),
            'TIMEOUT': sum(row['status'] == 'TIMEOUT' for row in part),
            'PAR2_180s': sum(float(row['totalSec']) if row['status'] == 'SAT' else 360 for row in part) / len(part),
            'largestCertifiedOptimumSolved': max((int(row['certifiedMinNodes']) for row in solved), default=None),
        }
    common = [pair for pair in cases.values() if all(pair[method]['status'] == 'SAT' for method in METHODS)]
    ratios = [float(pair['ATLAS-B']['totalSec']) / float(pair['MacroATLAS']['totalSec']) for pair in common]
    return {'cases': len(cases), 'byMethod': by_method, 'bothSAT': len(common),
            'macroFasterAmongBothSAT': sum(ratio > 1 for ratio in ratios),
            'medianAtlasOverMacroSec': statistics.median(ratios) if ratios else None,
            'geometricMeanAtlasOverMacroSec': math.exp(statistics.mean(math.log(ratio) for ratio in ratios)) if ratios else None}


def main():
    ab = rows('ab/rq4_paper_data.csv')
    profile = rows('profile/rq4c_profile_data.csv')
    combined = rows('combined/rq4c_paper_data.csv')
    check((len(ab), len(profile), len(combined)) == (36, 5, 41), 'Wrong record counts')
    check(len({(r['task'], r['variant'], r['repeat']) for r in combined}) == 41, 'Duplicate combined run')
    for section in ('ab', 'profile'):
        check(sha(section + '/plan.json') == (ROOT / section / 'plan.sha256').read_text().split()[0], 'Plan SHA mismatch')
        plan, state = data(section + '/plan.json'), data(section + '/state.json')
        check(plan['strictOnce'] is True and plan['timeoutSec'] == 180.0 and
              all(p['repeats'] == 1 for p in plan['phases']) and state['status'] == 'COMPLETE',
              'Campaign protocol/state mismatch')
        check(data(section + '/correctness-gate.json')['status'] == 'PASSED', 'Correctness gate failed')
    source_commit = data('ab/plan.json')['environment']['commit']
    check(source_commit == data('profile/plan.json')['environment']['commit'], 'Source commits differ')
    check(sha('ab/rq4_paper_data.csv') == data('ab/rq4_summary.json')['paperCsvSha256'], 'A/B CSV SHA mismatch')
    check(sha('profile/rq4c_profile_data.csv') == data('profile/rq4c_profile_summary.json')['paperCsvSha256'], 'C CSV SHA mismatch')
    combined_summary = data('combined/rq4c_summary.json')
    check(sha('combined/rq4c_paper_data.csv') == combined_summary['paperCsvSha256'], 'Combined CSV SHA mismatch')
    check(sha('ab/rq4_paper_data.csv') == combined_summary['abCsvSha256'] and
          sha('profile/rq4c_profile_data.csv') == combined_summary['profileCsvSha256'], 'Combined source SHA mismatch')
    individual = {(r['task'], r['variant'], r['repeat']): r for r in ab + profile}
    for row in combined:
        source = individual[row['task'], row['variant'], row['repeat']]
        check(all(row[k] == source[k] for k in ('status', 'totalSec', 'B', 'b', 'K', 'qStates')),
              'Combined row differs from source')
    for section, derived in [('ab', ab), ('profile', profile)]:
        raw = rows(section + '/e8-synthetic/merged/raw.csv')
        check(len(raw) == len(derived) and all(r['repeat'] == '1' for r in raw), 'Raw run count/repeat mismatch')
        raw_index = {(r['task'], r['variant'], r['repeat']): r for r in raw}
        check(len(raw_index) == len(raw), 'Duplicate raw run')
        for row in derived:
            source = raw_index[row['task'], row['variant'], row['repeat']]
            check(all(row[k] == source[k] for k in ('status', 'totalSec', 'B', 'b', 'K')),
                  'Derived row differs from raw')
    audit = data('ab/rq4c_ab_audit.json')['rows']
    check(len(audit) == 36 and sum(r['observedCertificate'] is True for r in audit) == 28 and
          sum(r['observedCertificate'] is None for r in audit) == 8 and
          not any(r['observedCertificate'] is False for r in audit), 'Certificate audit failed')
    binary = [r for r in ab if r['axis'] == 'certified_binary_arity']
    check(all(r['B'] == r['K'] and int(r['b']) == int(r['axisValue']) - 1 for r in binary),
          'Binary structural control differs')
    q_values = [1, 2, 4, 8, 16]
    q_rows = sorted(profile, key=lambda row: int(row['requestedQ']))
    check([int(r['requestedQ']) for r in q_rows] == q_values and
          all(int(r['actualQ']) == int(r['requestedQ']) and r['B'] == '17' and r['b'] == '0' and
              r['status'] == 'SAT' and r['verification'] == 'PASSED' and r['learnedDagNodes'] == '3'
              for r in q_rows) and len({r['traceSetHash'] for r in q_rows}) == 1,
          'Profile control differs')
    archive = ROOT.parent / 'archives/rq4-certified-records-20260924.tar.gz'
    expected_archive_sha = archive.with_name(archive.name + '.sha256').read_text().split()[0]
    actual_archive_sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    check(actual_archive_sha == expected_archive_sha, 'Raw archive SHA mismatch')
    with tarfile.open(archive) as bundle:
        names = [item.name for item in bundle.getmembers()]
        for campaign, expected in (('rq4-certified-ab-once', 36), ('rq4-certified-profile-once', 5)):
            commands = [name for name in names if name.startswith(campaign + '/e8-synthetic/workers/')
                        and name.endswith('/command.json')]
            results = [name for name in names if name.startswith(campaign + '/e8-synthetic/workers/')
                       and name.endswith('/result.json')]
            check(len(commands) == len(results) == expected, 'Raw attempt count differs')
        check('rq4-certified-data/inputs/manifest.json' in names and
              not any(name.endswith('/source.bundle') for name in names), 'Archive content differs')
    analysis = {
        'sourceCommit': source_commit, 'runs': 41, 'certifiedSat': 28,
        'unresolvedTimeout': 8, 'profileSat': 5,
        'rawArchiveSha256': actual_archive_sha,
        'unary': summarize_axis(ab, 'certified_unary_depth'),
        'binary': summarize_axis(ab, 'certified_binary_arity'),
        'profile': [{key: row[key] for key in ('requestedQ', 'actualQ', 'fiberCount', 'vars',
                    'backendTotalClauses', 'encodingSec', 'solverSec', 'totalSec', 'learnedDagNodes')}
                    for row in q_rows],
        'profileQ16OverQ1': {key: float(q_rows[-1][key]) / float(q_rows[0][key])
                             for key in ('fiberCount', 'vars', 'backendTotalClauses', 'encodingSec',
                                         'solverSec', 'totalSec')},
        'sourceSha256': {str(p.relative_to(ROOT)): sha(p.relative_to(ROOT)) for p in
                         (ROOT/'ab/rq4_paper_data.csv', ROOT/'profile/rq4c_profile_data.csv',
                          ROOT/'combined/rq4c_paper_data.csv')},
    }
    (ROOT / 'analysis.json').write_text(json.dumps(analysis, indent=2, sort_keys=True) + '\n')
    print(json.dumps(analysis, indent=2))


if __name__ == '__main__':
    main()
