#!/usr/bin/env python3
"""Prespecified RQ4 scaling grid, per-instance inspection, and paper tables."""
import argparse
import collections
import csv
import json
import pathlib
import statistics
import subprocess

from common import ATLAS, FIELDS, digest, java_command, save_csv, save_json, sha256
from synthetic import write_task


SEED = 20260924


def generate(output, seed=SEED):
    if output.exists():
        raise ValueError("RQ4 input directory already exists")
    records = []

    def add(name, formula, B, b, ap, length, axis, value, regime, unary_depth, binary_nodes,
            required=(), traces=4, case_seed=None):
        record = write_task(output, name, formula, seed + len(records) if case_seed is None else case_seed,
                            B, b, ap, traces, length, required_propositions=required)
        record.update(axis=axis, axisValue=value, regime=regime, targetUnaryDepth=unary_depth,
                      targetBinaryNodes=binary_nodes)
        save_json((output / name).with_suffix('.json'), record)
        records.append(record)

    # One factor at a time. All B-series tasks use identical examples and target.
    for B in [7, 11, 15, 21, 31, 41]:
        add('favorable_B/B%02d' % B, 'X('*6+'x0'+')'*6, B, 1, 1, 12,
            'B', B, 'small_b_long_unary', 6, 0, case_seed=seed+1)
    # Fixed B, b, traces and trace length; only target unary depth changes.
    for depth in [2, 4, 6, 8, 12, 16, 20, 30]:
        add('unary_depth/d%02d' % depth, 'X('*depth+'x0'+')'*depth, 31, 1, 1, 32,
            'unary_depth', depth, 'small_b_long_unary', depth, 0, case_seed=seed+2)
    conjunction='&(&(x0,x1),&(x2,x3))'
    for b in [3, 4, 5, 6, 7]:
        add('binary_budget/b%02d' % b, conjunction, 15, b, 4, 10,
            'b', b, 'large_b_short_unary', 0, 3, case_seed=seed+3)
    for B in [7, 11, 15, 21, 31]:
        # K=min(B,3b+2)=B (or B-1), so structural compression is absent.
        b=max(3,(B-2+2)//3)
        add('control_B/B%02d' % B, conjunction, B, b, 4, 10,
            'B', B, 'large_b_short_unary', 0, 3, case_seed=seed+3)
    q_target='&(x0,&(x1,x2))'
    for count in [0, 1, 2, 3]:
        add('constraint_states/r%02d' % count, q_target, 11, 2, 3, 10,
            'required_count', count, 'q_axis', 0, 2,
            required=tuple('x%d' % i for i in range(count)), case_seed=seed+4)
    add('shape/fxg', 'F('+'X('*8+'G(x0)'+')'*8+')', 15, 1, 1, 16,
        'shape', 'FX8G', 'small_b_long_unary', 10, 0, case_seed=seed+5)
    add('shape/branches', '&('+'X('*6+'x0'+')'*6+',F('+'X('*4+'x1'+')'*4+'))',
        21, 1, 2, 16, 'shape', 'two_branches', 'small_b_long_unary', 6, 1,
        case_seed=seed+6)
    save_json(output/'manifest.json', dict(seed=seed, cases=len(records), runs=2*len(records), tasks=records,
        suiteHash=digest(records), stoppingRule='All prespecified cases; no outcome-based pruning or replacement',
        labels='Independent lasso evaluator; target is a witness, not a certified minimum'))
    print(json.dumps(dict(cases=len(records), runs=2*len(records), output=str(output))))


def inspect(ready, java):
    root=ready/'matched_u_free'
    names=(ready/'matched/supported_tasks.txt').read_text().splitlines()
    all_names=sorted(p.relative_to(root).as_posix() for p in root.rglob('*.trace'))
    if sorted(names)!=all_names:
        raise ValueError('Every preregistered RQ4 task must have analyzer support')
    rows=[]
    for name in names:
        task=root/name
        data=json.loads(task.with_suffix('.json').read_text())
        if 'axis' not in data:
            raise ValueError('Missing RQ4 preregistration: '+name)
        folder=ready/'inspection'/pathlib.Path(name).with_suffix('')
        folder.mkdir(parents=True,exist_ok=False)
        subprocess.run(java_command(java)+['--mode','inspect','--file',str(task),'--B',str(data['B']),
                     '--b',str(data['b']),'--output',str(folder)],cwd=ATLAS,check=True,
                     stdout=subprocess.DEVNULL)
        result=json.loads((folder/'inspect.json').read_text())
        if result.get('supported') is not True:
            raise ValueError('Actual per-task B/b unsupported: %s %s' % (name,result))
        if result['nodeBudget']!=data['B'] or result['binaryBudget']!=data['b']:
            raise ValueError('Analyzer budget mismatch: '+name)
        data.update(p=result['protectedCount'],K=result['anchorSlotBudget'],q=result['constraintStateCount'],
                    recognizedFeatures=result['recognizedFeatures'],
                    compressionPotential=1-result['anchorSlotBudget']/data['B'])
        save_json(task.with_suffix('.json'),data)
        rows.append(data)
    qs=[r['q'] for r in rows if r['axis']=='required_count']
    if len(set(qs))<3 or qs!=sorted(qs):
        raise ValueError('Constraint-state axis did not create at least three increasing q levels: '+str(qs))
    save_json(ready/'rq4-inspected-manifest.json',dict(cases=len(rows),runs=2*len(rows),
        tasks=rows,suiteHash=digest(rows),qLevels=qs,
        note='q is the actual reachable minimized constraint automaton state count at each task B/b'))
    print(json.dumps(dict(cases=len(rows),runs=2*len(rows),qLevels=qs)))


def rows_so_far(campaign):
    plan=json.loads((campaign/'plan.json').read_text())
    phase=next(p for p in plan['phases'] if p['id']=='e8-synthetic')
    rows=[]
    for worker in phase['workers']:
        file=pathlib.Path(worker['output'])/'raw.csv'
        if file.exists():
            with file.open() as f:rows.extend(csv.DictReader(f))
    return phase,rows


def status(campaign):
    phase,rows=rows_so_far(campaign)
    expected=2*len(phase['tasks'])
    counts=collections.Counter(r['variant'] for r in rows)
    statuses={v:dict(collections.Counter(r['status'] for r in rows if r['variant']==v))
              for v in ('atlas-b','macro')}
    state=json.loads((campaign/'state.json').read_text())['status']
    report='RQ4 ATLAS-B %d/%d | MacroATLAS %d/%d | total %d/%d | state=%s' % (
        counts['atlas-b'],len(phase['tasks']),counts['macro'],len(phase['tasks']),len(rows),expected,state)
    print(report)
    print(json.dumps(statuses,ensure_ascii=False))
    return state


def report(campaign):
    phase,rows=rows_so_far(campaign)
    manifest=json.loads((pathlib.Path(phase['root']).parent/'rq4-inspected-manifest.json').read_text())
    tasks={r['task']:r for r in manifest['tasks']}
    expected={(name,variant) for name in tasks for variant in ('atlas-b','macro')}
    actual=[(r['task'],r['variant']) for r in rows]
    if len(actual)!=len(set(actual)) or set(actual)!=expected:
        raise ValueError('Incomplete or duplicate RQ4 outcomes: %d/%d' % (len(actual),len(expected)))
    if json.loads((campaign/'state.json').read_text())['status']!='COMPLETE':
        raise ValueError('RQ4 campaign has not completed')
    if not (campaign/'e8-synthetic/complete.json').exists():
        raise ValueError('Merged/validated campaign result is missing')
    merged=campaign/'e8-synthetic/merged/raw.csv'
    if not merged.exists():raise ValueError('Merged raw results missing')
    with merged.open() as f:
        merged_keys={(r['task'],r['variant']) for r in csv.DictReader(f)}
    if merged_keys != expected:
        raise ValueError('Merged coverage mismatch')
    data=[]
    plan=json.loads((campaign/'plan.json').read_text())
    extra=['axis','axisValue','regime','target','targetUnaryDepth','targetBinaryNodes','AP','positive','negative',
           'length','profile','requiredPropositions','q','compressionPotential','recognizedFeatures','seed']
    for r in sorted(rows,key=lambda x:(x['task'],x['variant'])):
        task=tasks[r['task']]
        enriched=dict(r)
        for key in extra:enriched[key]=task.get(key,'')
        enriched['qStates']=task['q']
        enriched['K']=task['K']
        enriched['p']=task['p']
        enriched['B']=task['B']
        enriched['b']=task['b']
        enriched['algorithm']='ATLAS-B' if r['variant']=='atlas-b' else 'MacroATLAS'
        enriched['runCommit']=plan.get('environment',{}).get('commit','')
        enriched['timeoutSec']=plan.get('timeoutSec','')
        enriched['requiredPropositions']=';'.join(task['requiredPropositions'])
        enriched['solved']=r['status'] in ('SAT','UNSAT') and (r['status']=='UNSAT' or r['verification']=='PASSED')
        data.append(enriched)
    fields=['algorithm']+list(FIELDS)+extra+['runCommit','timeoutSec','solved']
    save_csv(campaign/'rq4_paper_data.csv',data,fields)
    by={(r['task'],r['variant']):r for r in data}
    pairs=[]
    for task in manifest['tasks']:
        a=by[(task['task'],'atlas-b')];m=by[(task['task'],'macro')]
        both=bool(a['solved'] and m['solved'])
        pairs.append(dict(task=task['task'],axis=task['axis'],axisValue=task['axisValue'],regime=task['regime'],
            B=task['B'],b=task['b'],p=task['p'],K=task['K'],q=task['q'],
            compressionPotential=task['compressionPotential'],targetUnaryDepth=task['targetUnaryDepth'],
            atlasStatus=a['status'],macroStatus=m['status'],atlasSec=a['totalSec'],macroSec=m['totalSec'],
            speedup=float(a['totalSec'])/float(m['totalSec']) if both and float(m['totalSec'])>0 else '',
            bothSolved=both,statusAgreement=a['status']==m['status'] if both else '',
            objectiveAgreement=(a['objectivePrimary']==m['objectivePrimary'] and a['objectiveSecondary']==m['objectiveSecondary']) if both else ''))
    save_csv(campaign/'rq4_pairs.csv',pairs,list(pairs[0]))
    groups=[]
    for regime,axis,value,variant in sorted({(r['regime'],r['axis'],str(r['axisValue']),r['variant']) for r in data}):
        subset=[r for r in data if (r['regime'],r['axis'],str(r['axisValue']),r['variant'])==
                (regime,axis,value,variant)]
        times=[float(r['totalSec']) for r in subset if r['solved']]
        groups.append(dict(regime=regime,axis=axis,axisValue=value,algorithm=variant,
                           cases=len(subset),solved=len(times),statuses=dict(collections.Counter(r['status'] for r in subset)),
                           medianSolvedSec=statistics.median(times) if times else None))
    summary=dict(cases=len(tasks),runs=len(data),statusCounts={v:dict(collections.Counter(r['status'] for r in data if r['variant']==v))
        for v in ('atlas-b','macro')},bothSolved=sum(p['bothSolved'] for p in pairs),
        statusDisagreements=[p['task'] for p in pairs if p['statusAgreement'] is False],
        objectiveDisagreements=[p['task'] for p in pairs if p['objectiveAgreement'] is False],
        perAxis=groups,manifestSha256=sha256(pathlib.Path(phase['root']).parent/'rq4-inspected-manifest.json'),
        rawSha256=sha256(merged),paperCsvSha256=sha256(campaign/'rq4_paper_data.csv'),
        note='One attempt per algorithm/case; timeout/error included, speedup only where both solved. Target depth is a construction parameter, not necessarily the learned formula depth.')
    save_json(campaign/'rq4_summary.json',summary)
    print(json.dumps(dict(cases=summary['cases'],runs=summary['runs'],statusCounts=summary['statusCounts'],
        bothSolved=summary['bothSolved'],paperFile=str(campaign/'rq4_paper_data.csv')),ensure_ascii=False,indent=2))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command',required=True)
    g=sub.add_parser('generate');g.add_argument('--output',type=pathlib.Path,required=True);g.add_argument('--seed',type=int,default=SEED)
    i=sub.add_parser('inspect');i.add_argument('--ready',type=pathlib.Path,required=True);i.add_argument('--java',default='java')
    s=sub.add_parser('status');s.add_argument('--campaign',type=pathlib.Path,required=True)
    r=sub.add_parser('report');r.add_argument('--campaign',type=pathlib.Path,required=True)
    a=p.parse_args()
    if a.command=='generate':generate(a.output.resolve(),a.seed)
    elif a.command=='inspect':inspect(a.ready.resolve(),a.java)
    elif a.command=='status':status(a.campaign.resolve())
    else:report(a.campaign.resolve())


if __name__=='__main__':main()
