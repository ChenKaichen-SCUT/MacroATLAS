"""Recompute and verify all 623 frozen translation scopes without solving."""
import collections, hashlib, csv
from pathlib import Path
SCOPES = (5, 7, 9, 11, 15)
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

def main():
    with (Path(__file__).parent/'benchmark/manifest.csv').open() as f:
        rows=list(csv.DictReader(f))
    for r in rows:r['inputSha256']=r['input_sha256']
    first=selected(rows)
    old={'jobs':[dict(r,scope=s) for r,_,s in first], 'attemptsPerMethodCaseScope':1, 'sourceSha256':'frozen'}
    all_picks=first+remaining(rows,old,'frozen')
    assert len(all_picks)==623
    assert all(int(r['scope'])==s for r,_,s in all_picks)
    print('PASS: all 623 per-instance translation scopes match the frozen manifest')
if __name__=='__main__':main()
