#!/usr/bin/env python3
"""Recompute manuscript statistics from frozen CSVs; fail before writing on a mismatch.

No learner or solver is run. Blank measurements remain blank. Each paired
translation contributes once, although its ratio is repeated in the raw table.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
DECISIVE = {'SAT', 'UNSAT'}
METHODS = ('ATLAS-B', 'MacroATLAS')


def rows(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def raw(name):
    return rows(ROOT / 'results/raw' / name)


def pairs(records):
    result = {}
    for r in records:
        bucket = result.setdefault(r['task'], {})
        assert r['algorithm'] not in bucket, ('Duplicate observation', r['task'])
        bucket[r['algorithm']] = r
    assert all(set(p) == set(METHODS) for p in result.values())
    return result


def check_inputs():
    manifests = [('benchmark/manifest.csv', 623), ('small/manifest.csv', 1000),
                 ('unary/manifest.csv', 12), ('discussion/binary_manifest.csv', 6),
                 ('discussion/profile_manifest.csv', 5)]
    for relative, n in manifests:
        manifest = ROOT / 'datasets' / relative
        data = rows(manifest)
        assert len(data) == n and len({r['task'] for r in data}) == n
        for r in data:
            assert hashlib.sha256((manifest.parent/r['task']).read_bytes()).hexdigest() == r['input_sha256']
            if 'original_sha256' in r:
                assert hashlib.sha256((ROOT/'datasets/original'/r['task']).read_bytes()).hexdigest() == r['original_sha256']
        print(f'PASS inputs: {relative}: {n} cases')
    benchmark={r['task']:r for r in rows(ROOT/'datasets/benchmark/manifest.csv')}
    small={r['task']:r for r in rows(ROOT/'datasets/small/manifest.csv')}
    for name,manifest in [('rq1_small_smt.csv',small),('rq1_benchmark_smt.csv',benchmark),
                          ('rq2_translation.csv',benchmark),('rq3_performance.csv',benchmark)]:
        data=raw(name)
        assert {r['task'] for r in data}==set(manifest),name
        for r in data:
            m=manifest[r['task']]
            assert (r['B'],r['b'])==(m['B'],m['b'])
            if 'inputSha256' in r:assert r['inputSha256']==m['input_sha256']
    final=[json.loads(line) for line in (ROOT/'results/evidence/benchmark_sat_outputs.jsonl').read_text().splitlines()]
    run={(r['task'],r['algorithm']):r for r in raw('rq3_performance.csv')}
    assert len(final)==len({(r['task'],r['algorithm']) for r in final})==727
    assert {(r['task'],r['algorithm']) for r in final}=={k for k,r in run.items() if r['status']=='SAT'}
    for r in final:
        reference=run[r['task'],r['algorithm']]
        assert r['formula'] and r['verification']['status']=='PASSED'
        assert all(str(r[k])==reference[k] for k in ['objectivePrimary','objectiveSecondary'])
    print('PASS final SAT outputs: 727 formulas, objectives, and archived verification records')


def rq1():
    small, benchmark = raw('rq1_small_smt.csv'), raw('rq1_benchmark_smt.csv')
    assert len(small) == 1000 and len(benchmark) == 623
    assert Counter(r['oracleStatus'] for r in small) == {'SAT': 819, 'UNSAT': 181}
    for r in small:
        assert r['macroStatus'] == r['oracleStatus']
        if r['oracleStatus'] == 'SAT':
            assert (r['macroPrimary'], r['macroSecondary']) == (r['oraclePrimary'], r['oracleSecondary'])
            assert r['macroSatVerified'] == r['oracleSatVerified'] == 'True'
    assert Counter(r['oracleStatus'] for r in benchmark) == {'OPTIMAL': 457, 'UNSAT': 32, 'TIMEOUT': 134}
    joint = [r for r in benchmark if r['oracleStatus'] in {'OPTIMAL', 'UNSAT'} and r['MacroATLASStatus'] in DECISIVE]
    sat = [r for r in joint if r['oracleStatus'] == 'OPTIMAL']
    assert len(joint) == 393 and len(sat) == 384
    for r in joint:
        assert r['MacroATLASStatus'] == ('SAT' if r['oracleStatus'] == 'OPTIMAL' else 'UNSAT')
        if r in sat:
            assert r['MacroATLASObjectiveSecondary'] == r['optimalSize']
            if r['objectiveKind'] == 'REPAIR':
                assert r['MacroATLASObjectivePrimary'] == r['optimalRetainedEdges']
            assert r['MacroATLASVerification'] == 'PASSED'
    result = [dict(group='Small', N=1000, oracle_decisive=1000, joint_decisive=1000,
                   status_agreements=1000, joint_sat=819, optimum_agreements=819),
              dict(group='Benchmark', N=623, oracle_decisive=489, joint_decisive=393,
                   status_agreements=393, joint_sat=384, optimum_agreements=384)]
    print('PASS Table 1:', json.dumps(result))
    return result


def rq2():
    data = raw('rq2_translation.csv'); by = pairs(data)
    assert len(by) == 623
    result, observations = [], []
    selectors = [('Unconstrained', lambda r: r['constraintGroup'] == 'unconstrained'),
                 ('Constrained', lambda r: r['constraintGroup'] == 'constrained')]
    selectors += [(label, lambda r, f=family: r['family'] == f) for label, family in
                  [('Peterson', 'peterson'), ('Robot', 'robot'), ('Voting', 'voting_machine'), ('Weakening', 'weakening')]]
    expected = [(485,459,459,480,213,458,.98,1.53),(138,114,114,138,98,105,4.92,6.88),
                (30,30,30,30,30,30,11.30,12.86),(20,20,20,20,20,20,9.52,13.52),
                (10,10,10,10,10,10,2.82,3.76),(78,54,54,78,38,45,1.15,1.63)]
    for (label, predicate), ex in zip(selectors, expected):
        selected = [p for p in by.values() if predicate(p['MacroATLAS'])]
        complete = [p for p in selected if all(r['status'] == 'TRANSLATED_ONLY' for r in p.values())]
        cv, cc = [], []
        for p in selected:
            paired = p in complete
            assert all((r['pairedTranslated'] == 'True') == paired for r in p.values())
            if not paired:
                assert all(r['C_V'] == r['C_C'] == '' for r in p.values())
                continue
            a, m = p['ATLAS-B'], p['MacroATLAS']
            v, c = int(a['vars'])/int(m['vars']), int(a['backendTotalClauses'])/int(m['backendTotalClauses'])
            assert all(math.isclose(float(r['C_V']), v, rel_tol=1e-12) and math.isclose(float(r['C_C']), c, rel_tol=1e-12) for r in p.values())
            cv.append(v); cc.append(c)
            if label in {'Unconstrained', 'Constrained'}:
                observations.append(dict(task=m['task'], group=label, family=m['family'], C_V=v, C_C=c))
        r = dict(group=label, N=len(selected), paired=len(complete),
                 translation_atlas=sum(p['ATLAS-B']['status']=='TRANSLATED_ONLY' for p in selected),
                 translation_macro=sum(p['MacroATLAS']['status']=='TRANSLATED_ONLY' for p in selected),
                 macro_variables_smaller=sum(v>1 for v in cv), macro_clauses_smaller=sum(c>1 for c in cc),
                 median_C_V=statistics.median(cv), median_C_C=statistics.median(cc))
        assert tuple(r[k] for k in list(r)[1:7]) == ex[:6], r
        assert round(r['median_C_V'],2) == ex[6] and round(r['median_C_C'],2) == ex[7], r
        result.append(r)
    assert len(observations) == len({r['task'] for r in observations}) == 573
    print('PASS Table 2 / Figure 2: 573 unique pairs; 311 variable reductions; 563 clause reductions')
    for r in result: print(json.dumps(r))
    return result, observations


def rq3():
    data = raw('rq3_performance.csv'); by = pairs(data)
    assert len(by) == 623
    expected = {'b=2': [(316,3,251,14,319,177.59),(345,9,230,0,354,158.64)],
                'b=3': [(27,0,12,0,27,120.10),(39,0,0,0,39,23.97)],
                'Overall': [(343,3,263,14,346,173.99),(384,9,230,0,393,150.21)]}
    result = []
    for group, b in [('b=2','2'), ('b=3','3'), ('Overall',None)]:
        for i, method in enumerate(METHODS):
            rr = [r for r in data if r['algorithm']==method and (b is None or r['b']==b)]
            counts=Counter(r['status'] for r in rr)
            assert set(counts) <= DECISIVE | {'TIMEOUT','ERROR'}
            for r in rr:
                solved=r['status'] in DECISIVE
                assert (r['solved']=='True') == solved
                assert not solved or 0 < float(r['totalSec']) <= 180
                assert math.isclose(float(r['par2Sec']), float(r['totalSec']) if solved else 360, rel_tol=1e-12)
            record=dict(group=group,method=method,N=len(rr),**{s:counts[s] for s in ['SAT','UNSAT','TIMEOUT','ERROR']},
                        solved=counts['SAT']+counts['UNSAT'],par2_mean=statistics.mean(float(r['par2Sec']) for r in rr))
            actual=tuple(record[k] for k in ['SAT','UNSAT','TIMEOUT','ERROR','solved'])+(round(record['par2_mean'],2),)
            assert actual==expected[group][i],record
            result.append(record)
    ratios=[float(p['ATLAS-B']['totalSec'])/float(p['MacroATLAS']['totalSec']) for p in by.values() if all(r['status'] in DECISIVE for r in p.values())]
    speed=dict(joint_solved=len(ratios),median=statistics.median(ratios),geometric_mean=statistics.geometric_mean(ratios))
    assert speed['joint_solved']==331 and round(speed['median'],2)==1.25 and round(speed['geometric_mean'],2)==1.22
    print('PASS Table 3:',json.dumps(result));print('PASS paired runtime:',json.dumps(speed))
    return result, [speed]


def rq4():
    data=raw('rq4_unary.csv');by=pairs(data)
    assert len(by)==12
    assert sorted(int(p['MacroATLAS']['axisValue']) for p in by.values())==[4,6,8,10,12,14,16,20,24,28,32,40]
    assert Counter(r['status'] for r in data if r['algorithm']=='ATLAS-B')=={'SAT':5,'TIMEOUT':7}
    assert Counter(r['status'] for r in data if r['algorithm']=='MacroATLAS')=={'SAT':12}
    result=[]
    for r in data:
        if r['status']=='SAT': assert int(r['objectiveSecondary'])==int(r['certifiedMinNodes'])==int(r['axisValue'])+1
        result.append(dict(task=r['task'],method=r['algorithm'],depth=int(r['axisValue']),status=r['status'],runtime_s=r['totalSec'],timeout_boundary_s=180))
    print('PASS Figure 3: 12 unary cases; ATLAS-B 5 SAT / 7 TIMEOUT; MacroATLAS 12 SAT')
    return result


def discussion():
    data=rows(ROOT/'results/discussion/certified_controls.csv')
    binary=[r for r in data if r['family']=='rq4c_binary']
    profile=[r for r in data if r['family']=='rq4c_profile']
    assert len(binary)==12 and len(profile)==5
    assert Counter(r['status'] for r in binary if r['algorithm']=='ATLAS-B')=={'SAT':6}
    assert Counter(r['status'] for r in binary if r['algorithm']=='MacroATLAS')=={'SAT':5,'TIMEOUT':1}
    by={(r['task'],r['algorithm']):r for r in data}
    for r in rows(ROOT/'results/discussion/plot_data.csv'):
        source=by[r['task'],r['algorithm']]
        assert r['status']==source['status'] and math.isclose(float(r['rawValue']),float(source[r['metric']]),rel_tol=1e-12)
        if r['foldIncrease']:
            base=by['rq4c_profile/q01.trace','MacroATLAS'][r['metric']]
            assert math.isclose(float(r['foldIncrease']),float(r['rawValue'])/float(base),rel_tol=1e-12)
    print('PASS Figure 4: 6 binary cases + 5 neutral-profile cases, q=1,2,4,8,16')


def main(output=None):
    check_inputs(); one=rq1(); two, obs=rq2(); three, speed=rq3(); four=rq4();discussion()
    if output:
        output=Path(output); output.mkdir(parents=True,exist_ok=True)
        for name, data in [('rq1',one),('rq2',two),('rq2_observations',obs),('rq3',three),('rq3_paired_runtime',speed),('rq4',four)]:
            with (output/(name+'.csv')).open('w',encoding='utf-8',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(data[0]),lineterminator='\n');w.writeheader();w.writerows(data)
        print('Wrote checked summary CSVs to',output)
    print('ALL MANUSCRIPT CONSISTENCY CHECKS PASSED')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,help='Write summaries only after every assertion passes')
    main(parser.parse_args().output)
