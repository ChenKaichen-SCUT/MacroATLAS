"""Outcome-independent, proportionally stratified selection of the paper workload."""
import collections
import csv
import json
import math
import random

from common import digest, sha256, save_csv, save_json, is_solved


def quotas(groups, count):
    """Largest-remainder allocation, with deterministic ties."""
    total = sum(len(v) for v in groups.values())
    exact = {k: count * len(v) / total for k, v in groups.items()}
    result = {k: math.floor(v) for k, v in exact.items()}
    for k in sorted(groups, key=lambda k: (-(exact[k] - result[k]), k))[:count - sum(result.values())]:
        result[k] += 1
    return result


def select(provenance, fraction, seed):
    if not 0 < fraction <= 1:
        raise ValueError("Paper fraction must be in (0, 1]")
    names = [r['task'] for r in provenance]
    if not names or len(names) != len(set(names)):
        raise ValueError("Empty/duplicate paper provenance")
    groups = collections.defaultdict(list)
    for r in provenance:
        groups[r['table']].append(r)
    allocation = quotas(groups, math.floor(len(names) * fraction + .5))
    if any(n == 0 for n in allocation.values()):
        raise ValueError("Fraction too small to represent every paper benchmark category")
    selected = []
    for table in sorted(groups):
        families = collections.defaultdict(list)
        for r in groups[table]:
            families[r['task'].split('/')[0]].append(r)
        for family, count in quotas(families, allocation[table]).items():
            ranked = sorted(families[family], key=lambda r: r['task'])
            random.Random(digest([seed, table, family])).shuffle(ranked)
            selected.extend(ranked[:count])
    return sorted(selected, key=lambda r: r['task'])


def selection_manifest(official, fraction, seed):
    source = official / 'paper-provenance.json'
    provenance = json.loads(source.read_text())
    if {r['task'] for r in provenance} != set((official / 'paper_tasks.txt').read_text().splitlines()):
        raise ValueError("Paper provenance differs from paper task list")
    selected = select(provenance, fraction, seed)
    with (official / 'matched/coverage.csv').open() as f:
        coverage = {r['task']: r for r in csv.DictReader(f)}
    records = [dict(r, matchedSupported=coverage[r['task']]['supported'] == 'true',
                    matchedReason=coverage[r['task']]['reason']) for r in selected]
    counts = []
    for table in sorted({r['table'] for r in provenance}):
        rows = [r for r in records if r['table'] == table]
        counts.append(dict(table=table, population=sum(r['table'] == table for r in provenance),
                           selected=len(rows), matchedSupported=sum(r['matchedSupported'] for r in rows)))
    return dict(fraction=fraction, seed=seed, sourceProvenanceSha256=sha256(source),
                population=len(provenance), selected=len(records), counts=counts, tasks=records,
                scope='Exploratory paper subset; not a full-workload result. No runtime/solved outcomes used for selection.',
                method='Largest remainder by paper table, then input family; deterministic seeded shuffle within each family. '
                       'Malformed and unsupported inputs remain selected; no replacement based on outcomes.')


def report(plan):
    """Separate paper categories in addition to the usual phase-wide summaries."""
    from pathlib import Path
    from analyze import aggregate, par2
    from validate_results import validate
    import statistics
    selection = plan.get('paperSubset')
    if not selection:
        return
    output = Path(plan['output']) / 'processed'
    tables = {r['task']: r['table'] for r in selection['tasks']}
    summaries = []
    for phase in plan['phases']:
        rows, manifest = validate(Path(plan['output']) / phase['id'] / 'merged')
        for group in selection['counts']:
            part = [r for r in rows if tables[r['task']] == group['table']]
            data = aggregate(part, manifest['timeoutSec'])
            left, right = ('atlas-b', 'macro') if phase['suite'] == 'matched' else ('original', 'auto')
            common = [(l, data[(t, right)]) for (t, v), l in data.items()
                      if v == left and (t, right) in data and l['solved'] and data[(t, right)]['solved']]
            for variant in {'original': ['original'], 'matched': ['atlas-b', 'macro'], 'auto': ['original', 'auto']}[phase['suite']]:
                runs = [r for r in part if r['variant'] == variant]
                tasks = [r for (t, v), r in data.items() if v == variant]
                summaries.append(dict(phase=phase['id'], table=group['table'], variant=variant,
                    selectedPaperTasks=group['selected'], eligibleTasks=len(tasks), runs=len(runs),
                    solvedTasks=sum(r['solved'] for r in tasks),
                    PAR2=par2(runs, manifest['timeoutSec']) if runs else None,
                    errors=sum(r['status'] == 'ERROR' for r in runs),
                    fallbackRuns=sum(r.get('fallbackUsed', '').lower() == 'true' for r in runs),
                    macroRuns=sum(r['solverMode'] == 'MACRO' for r in runs),
                    commonSolved=len(common),
                    medianSpeedup=statistics.median(float(l['totalSec']) / float(r['totalSec']) for l, r in common) if common else None))
    output.mkdir(exist_ok=True)
    save_csv(output / 'paper-subset-summary.csv', summaries, list(summaries[0]))
    save_json(output / 'paper-subset-summary.json', dict(selection=selection, summaries=summaries))
    print('Category summary:', output / 'paper-subset-summary.csv')
