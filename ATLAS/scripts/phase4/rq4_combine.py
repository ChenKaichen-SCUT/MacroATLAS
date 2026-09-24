#!/usr/bin/env python3
"""Combine the frozen RQ4 primary and follow-up tables without pooling runtimes."""

import argparse
import collections
import csv
import hashlib
import json
import statistics
from pathlib import Path


CAMPAIGNS = (('primary', '139.159.185.102'), ('followup', '110.41.76.57'))
METHODS = ('ATLAS-B', 'MacroATLAS')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path):
    with path.open(newline='') as source:
        reader = csv.DictReader(source)
        return reader.fieldnames, list(reader)


def write_csv(path, rows, fields):
    with path.open('w', newline='') as output:
        writer = csv.DictWriter(output, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def add_fields(fields, more):
    for field in more:
        if field not in fields:
            fields.append(field)


def read_campaign(name, server, directory):
    paper = directory / 'rq4_paper_data.csv'
    pairs = directory / 'rq4_pairs.csv'
    summary = json.loads((directory / 'rq4_summary.json').read_text())
    plan = json.loads((directory / 'plan.json').read_text())
    state = json.loads((directory / 'state.json').read_text())
    paper_fields, runs = read_csv(paper)
    pair_fields, matched = read_csv(pairs)
    if state['status'] != 'COMPLETE' or plan['strictOnce'] is not True:
        raise ValueError(f'{name}: campaign is not complete and strict-once')
    if any(phase['repeats'] != 1 for phase in plan['phases']):
        raise ValueError(f'{name}: non-single run in plan')
    if digest(paper) != summary['paperCsvSha256']:
        raise ValueError(f'{name}: source CSV checksum differs from summary')
    if len(runs) != 2 * len(matched) or len(matched) != summary['cases']:
        raise ValueError(f'{name}: incomplete source tables')
    keys = [(row['task'], row['algorithm']) for row in runs]
    tasks = {row['task'] for row in matched}
    expected = {(task, method) for task in tasks for method in METHODS}
    if len(keys) != len(set(keys)) or set(keys) != expected:
        raise ValueError(f'{name}: duplicate or missing task/method')
    if len(tasks) != len(matched):
        raise ValueError(f'{name}: duplicate pair row')
    by_key = {key: row for key, row in zip(keys, runs)}
    for row in matched:
        task = row['task']
        if (row['atlasStatus'], row['macroStatus']) != (
            by_key[(task, 'ATLAS-B')]['status'], by_key[(task, 'MacroATLAS')]['status']
        ):
            raise ValueError(f'{name}: pair status mismatch for {task}')
    timeout = float(plan['timeoutSec'])
    counts = {}
    for method in METHODS:
        own = [row for row in runs if row['algorithm'] == method]
        statuses = dict(sorted(collections.Counter(row['status'] for row in own).items()))
        costs = [2 * timeout if row['status'] in ('TIMEOUT', 'ERROR')
                 else float(row['totalSec']) for row in own]
        counts[method] = {
            'statuses': statuses,
            'solved': sum(row['status'] in ('SAT', 'UNSAT') for row in own),
            'par2Sec': statistics.mean(costs),
        }
    both = [row for row in matched if row['bothSolved'] == 'True']
    speeds = [float(row['speedup']) for row in both if row['speedup']]
    details = {
        'server': server,
        'cases': len(matched),
        'runs': len(runs),
        'timeoutSec': timeout,
        'runCommit': plan['environment']['commit'],
        'strictOnce': True,
        'counts': counts,
        'bothSolved': len(both),
        'pairedMedianSpeedup': statistics.median(speeds) if speeds else None,
        'macroOnlySolved': sum(row['atlasStatus'] not in ('SAT', 'UNSAT') and
                               row['macroStatus'] in ('SAT', 'UNSAT') for row in matched),
        'atlasOnlySolved': sum(row['macroStatus'] not in ('SAT', 'UNSAT') and
                               row['atlasStatus'] in ('SAT', 'UNSAT') for row in matched),
        'paperCsvSha256': digest(paper),
        'pairCsvSha256': digest(pairs),
        'summarySha256': digest(directory / 'rq4_summary.json'),
    }
    return paper_fields, pair_fields, runs, matched, details


def combine(primary, followup, output):
    output.mkdir(parents=True, exist_ok=True)
    all_runs, all_pairs = [], []
    run_fields, pair_fields = ['campaign', 'server'], ['campaign', 'server']
    campaigns = {}
    task_sets = []
    for (name, server), directory in zip(CAMPAIGNS, (primary, followup)):
        source_fields, source_pair_fields, runs, pairs, details = read_campaign(
            name, server, directory)
        add_fields(run_fields, source_fields)
        add_fields(pair_fields, source_pair_fields)
        all_runs.extend(dict(campaign=name, server=server, **row) for row in runs)
        all_pairs.extend(dict(campaign=name, server=server, **row) for row in pairs)
        campaigns[name] = details
        task_sets.append({row['task'] for row in pairs})
    if task_sets[0] & task_sets[1]:
        raise ValueError('Primary and follow-up case IDs overlap')
    paper = output / 'rq4_full_paper_data.csv'
    pairs = output / 'rq4_full_pairs.csv'
    write_csv(paper, all_runs, run_fields)
    write_csv(pairs, all_pairs, pair_fields)
    combined_counts = {}
    for method in METHODS:
        own = [row for row in all_runs if row['algorithm'] == method]
        combined_counts[method] = {
            'statuses': dict(sorted(collections.Counter(row['status'] for row in own).items())),
            'solved': sum(row['status'] in ('SAT', 'UNSAT') for row in own),
        }
    result = {
        'cases': len(all_pairs),
        'runs': len(all_runs),
        'campaigns': campaigns,
        'combinedCoverage': combined_counts,
        'bothSolved': sum(item['bothSolved'] for item in campaigns.values()),
        'macroOnlySolved': sum(item['macroOnlySolved'] for item in campaigns.values()),
        'atlasOnlySolved': sum(item['atlasOnlySolved'] for item in campaigns.values()),
        'paperCsvSha256': digest(paper),
        'pairCsvSha256': digest(pairs),
        'note': 'Campaigns differ in case design and server; report runtime and PAR-2 per campaign, not as a pooled speedup.',
    }
    (output / 'rq4_full_summary.json').write_text(
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--primary', type=Path, required=True)
    parser.add_argument('--followup', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(combine(args.primary, args.followup, args.output),
                     indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
