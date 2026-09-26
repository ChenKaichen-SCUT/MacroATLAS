#!/usr/bin/env python3
"""Frozen one-attempt campaign for independent RQ1 optimum certification."""

from __future__ import annotations

import argparse
import collections
import concurrent.futures
import csv
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

from rq1_exact_smt import BINARY, check_size, parse_task


SCRIPT = Path(__file__).resolve()
CORE = SCRIPT.with_name('rq1_exact_smt.py')
DEFAULT_ROOT = SCRIPT.parents[2] / 'generated/phase4-preflight/matched_u_free'
DEFAULT_TABLE = SCRIPT.parents[2] / 'experiment_artifacts/2026-09-25/rq2-full-623/summary/rq2_full_623_paper_data.csv'
DEFAULT_E4 = SCRIPT.parents[2] / 'experiment_artifacts/2026-09-23/combined/paired.csv'
PRIORITY = (
    '5to10Traces/0000.trace',
    'voting_machine/voting10.trace',
    'peterson/base/liveness1.trace',
    'robot/RRtrace/order2.trace',
    'robot/RAtrace/final21.trace',
    'weakening/weaken_antecedent/weaken_antecedent_10_10_10.trace',
    'weakening/weaken_consequent/weaken_consequent_10_10_10.trace',
)


def utc() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def save(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
    temp.replace(path)


def load(path: Path):
    return json.loads(path.read_text())


def job_dir(campaign: Path, case: dict) -> Path:
    return campaign/'jobs'/case['id']


def plan(args):
    out=args.output.resolve()
    if out.exists():raise ValueError('Campaign output must be new')
    table=list(csv.DictReader(args.table.open(newline='')))
    e4=list(csv.DictReader(args.e4.open(newline='')))
    if len(table)!=623 or len(e4)!=623 or {r['task'] for r in table}!={r['task'] for r in e4}:
        raise ValueError('Expected the same frozen 623 matched tasks')
    e4_by={r['task']:r for r in e4}
    cases=[]
    for row in table:
        src=args.root/row['task']
        task=parse_task(src,int(row['B']),int(row['b']),row['category'])
        if task.source_sha256!=row['inputSha256']:
            raise ValueError('Input SHA mismatch: '+row['task'])
        prior=e4_by[row['task']]
        case={k:row[k] for k in ('task','family','category','B','b','inputSha256')}
        case['id']=hashlib.sha256(row['task'].encode()).hexdigest()[:20]
        case['e4']={k:prior[k] for k in ('atlasBStatus','macroStatus','atlasBObjectivePrimary',
            'atlasBObjectiveSecondary','macroObjectivePrimary','macroObjectiveSecondary')}
        cases.append(case)
    if len({c['id'] for c in cases})!=623:raise ValueError('Case-id collision')
    out.mkdir(parents=True)
    for case in cases:
        source=args.root/case['task']
        target=out/'inputs'/case['task']
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
    (out/'code').mkdir()
    shutil.copy2(SCRIPT,out/'code'/SCRIPT.name)
    shutil.copy2(CORE,out/'code'/CORE.name)
    p={'schemaVersion':1,'createdUtc':utc(),'cases':cases,'expectedCases':623,
       'inputTableSha256':sha(args.table),'e4PairedSha256':sha(args.e4),
       'encodingSha256':sha(out/'code'/CORE.name),'controllerSha256':sha(out/'code'/SCRIPT.name),
       'sourceCommit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=SCRIPT.parents[3],text=True).strip(),
       'python':sys.version,'z3Version':__import__('z3').get_version_string(),
       'method':'independent finite DAG + concrete lasso semantics + exact SAT/UNSAT at every smaller size',
       'maxEncodedSize':args.max_size,'caseTimeoutSec':args.case_timeout,'solverTimeoutSec':args.solver_timeout,
       'memoryLimitGiB':args.memory_gib,
       'repairPrimary':'Require all distinct retained old edges; this is the absolute cardinality maximum',
       'oneAttemptPerCase':True}
    save(out/'plan.json',p)
    (out/'plan.sha256').write_text(sha(out/'plan.json')+'  plan.json\n')
    shutil.copy2(args.table,out/'source-rq2-paper-data.csv')
    shutil.copy2(args.e4,out/'source-e4-paired.csv')
    save(out/'state.json',{'status':'READY','createdUtc':utc()})
    print('Prepared 623 frozen cases at',out)


def check_plan(campaign: Path):
    p=load(campaign/'plan.json')
    if sha(campaign/'plan.json')!=(campaign/'plan.sha256').read_text().split()[0]:
        raise ValueError('Frozen plan checksum mismatch')
    if sha(campaign/'code'/CORE.name)!=p['encodingSha256'] or sha(campaign/'code'/SCRIPT.name)!=p['controllerSha256']:
        raise ValueError('Frozen code changed')
    if __import__('z3').get_version_string()!=p['z3Version']:
        raise ValueError('Z3 version changed')
    return p


def formula(witness: dict) -> str:
    nodes=witness['nodes']
    def render(i):
        x=nodes[i]
        if x['label'].startswith('x'):return x['label']
        if x['label'] in BINARY:return x['label']+'('+render(x['left'])+','+render(x['right'])+')'
        return x['label']+'('+render(x['left'])+')'
    return render(len(nodes)-1)


def worker(args):
    campaign=args.campaign.resolve()
    p=check_plan(campaign)
    case=next(c for c in p['cases'] if c['id']==args.id)
    job=job_dir(campaign,case)
    task=parse_task(campaign/'inputs'/case['task'],int(case['B']),int(case['b']),case['category'])
    if task.source_sha256!=case['inputSha256']:raise ValueError('Input changed after plan')
    if case['category']=='repair':
        kept_max=5 if 'G0' in task.custom else 4
    else:kept_max=0
    limit=min(task.B,p['maxEncodedSize'])
    started=time.monotonic()
    steps=[]
    final=None
    try:
        for size in range(1,limit+1):
            remaining=p['caseTimeoutSec']-(time.monotonic()-started)
            if remaining<2:
                final={'status':'TIMEOUT','reason':'CASE_DEADLINE'}
                break
            record=check_size(task,size,job/f'size_{size:03d}',
                              int(min(p['solverTimeoutSec'],remaining-1)*1000),kept_max)
            steps.append({k:record[k] for k in ('size','status','wallSec','querySha256','reasonUnknown')})
            if record['status']=='sat':
                witness=load(job/f'size_{size:03d}'/'witness.json')
                final={'status':'OPTIMAL','objectiveKind':'REPAIR' if kept_max else 'MIN_EXPANDED_SIZE',
                       'objectivePrimary':kept_max,'objectiveSecondary':size,
                       'witness':witness,'formula':formula(witness),
                       'certificate':'Every smaller exact size UNSAT; this size SAT with independently checked witness',
                       'maxKeptReason':'All old edges retained, no greater count exists' if kept_max else ''}
                break
            if record['status']=='unknown':
                final={'status':'TIMEOUT' if 'timeout' in record['reasonUnknown'].lower() else 'UNKNOWN',
                       'reason':'SMT_'+record['reasonUnknown']}
                break
        if final is None:
            if limit==task.B and not kept_max:
                final={'status':'UNSAT','certificate':'Every exact size 1..B is UNSAT'}
            else:
                final={'status':'UNKNOWN','reason':'SIZE_CAP' if limit<task.B else 'REPAIR_MAX_KEPT_NOT_FOUND'}
        final.update(task=case['task'],caseId=case['id'],category=case['category'],B=task.B,b=task.b,
                     inputSha256=task.source_sha256,steps=steps,checkedSizes=len(steps),
                     wallSec=time.monotonic()-started,finishedUtc=utc())
        save(job/'result.json',final)
    except Exception as e:
        save(job/'result.json',{'task':case['task'],'caseId':case['id'],
                                'status':'UNKNOWN' if isinstance(e,MemoryError) else 'ERROR',
                                'reason':f'{type(e).__name__}: {e}','steps':steps,
                                'wallSec':time.monotonic()-started,'finishedUtc':utc()})
        raise


def _launch(campaign: Path, p: dict, case: dict, cpu: int):
    job=job_dir(campaign,case)
    if (job/'result.json').exists():return load(job/'result.json')
    if job.exists():
        record={'task':case['task'],'caseId':case['id'],'status':'UNKNOWN',
                'reason':'INTERRUPTED_PREVIOUS_ATTEMPT','wallSec':'','finishedUtc':utc()}
        save(job/'result.json',record)
        return record
    job.mkdir(parents=True)
    command=['prlimit',f"--as={p['memoryLimitGiB']*1024**3}",'--',
             'taskset','-c',str(cpu),sys.executable,str(campaign/'code'/SCRIPT.name),
             'worker','--campaign',str(campaign),'--id',case['id']]
    save(job/'started.json',{'task':case['task'],'command':command,'startedUtc':utc(),
                              'inputSha256':case['inputSha256'],'attempt':1})
    begin=time.monotonic()
    with (job/'stdout.log').open('w') as out,(job/'stderr.log').open('w') as err:
        process=subprocess.Popen(command,stdout=out,stderr=err,start_new_session=True)
        try:
            code=process.wait(timeout=p['caseTimeoutSec']+5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGKILL)
            code=process.wait()
            save(job/'result.json',{'task':case['task'],'caseId':case['id'],'status':'TIMEOUT',
                'reason':'EXTERNAL_WALL_TIMEOUT','wallSec':time.monotonic()-begin,'finishedUtc':utc()})
    if not (job/'result.json').exists():
        save(job/'result.json',{'task':case['task'],'caseId':case['id'],'status':'ERROR',
            'reason':f'Worker exited {code} without result','wallSec':time.monotonic()-begin,'finishedUtc':utc()})
    return load(job/'result.json')


def run(args):
    campaign=args.campaign.resolve()
    p=check_plan(campaign)
    cases=sorted(p['cases'],key=lambda c:(0 if c['task'] in PRIORITY else 1,
        PRIORITY.index(c['task']) if c['task'] in PRIORITY else 0,
        int(c['B']),c['task']))
    if args.workers<1 or len(args.cpus)<args.workers:raise ValueError('Supply one disjoint CPU per worker')
    started=time.monotonic()
    save(campaign/'state.json',{'status':'RUNNING','startedUtc':utc(),'workers':args.workers,'cpus':args.cpus})
    def run_shard(shard,cpu):
        for case in shard:
            try:result=_launch(campaign,p,case,cpu)
            except Exception as e:
                print('LAUNCH_ERROR',case['task'],type(e).__name__,e,flush=True)
                continue
            print(utc(),case['task'],result['status'],result.get('objectiveSecondary',''),
                  f"{float(result['wallSec']):.1f}s" if result.get('wallSec') not in ('',None) else '',flush=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures=[executor.submit(run_shard,cases[i::args.workers],args.cpus[i]) for i in range(args.workers)]
        for future in concurrent.futures.as_completed(futures):future.result()
    state={'status':'COMPLETE','finishedUtc':utc(),'campaignWallSec':time.monotonic()-started}
    save(campaign/'state.json',state)
    summarize(campaign,p)


def summarize(campaign: Path,p=None):
    p=p or load(campaign/'plan.json')
    prior={}
    if (campaign/'previous-attempts.csv').exists():
        with (campaign/'previous-attempts.csv').open(newline='') as handle:
            prior={item['task']:item for item in csv.DictReader(handle)}
    records=[]
    for case in p['cases']:
        path=job_dir(campaign,case)/'result.json'
        result=load(path) if path.exists() else {'status':'MISSING','task':case['task']}
        row={**case,**case['e4'],'oracleStatus':result['status'],'oraclePrimary':result.get('objectivePrimary',''),
             'oracleSecondary':result.get('objectiveSecondary',''),'wallSec':result.get('wallSec',''),
             'checkedSizes':result.get('checkedSizes',''),'reason':result.get('reason',''),
             'formula':result.get('formula',''),'certificatePath':str(path.relative_to(campaign)) if path.exists() else '',
             'previousStatus':prior.get(case['task'],{}).get('previousStatus',''),
             'previousReason':prior.get(case['task'],{}).get('previousReason',''),
             'evidenceSource':'INHERITED' if (job_dir(campaign,case)/'inherited-from.json').exists() else 'CURRENT'}
        for prefix,method in (('atlasB','ATLAS-B'),('macro','MacroATLAS')):
            status=case['e4'][prefix+'Status']
            if result['status']=='OPTIMAL' and status=='SAT':
                same=(str(result['objectivePrimary'])==case['e4'][prefix+'ObjectivePrimary'] and
                      str(result['objectiveSecondary'])==case['e4'][prefix+'ObjectiveSecondary'])
                row[method+'Comparison']='AGREE' if same else 'DISAGREE_OBJECTIVE'
            elif result['status']=='UNSAT' and status=='UNSAT':row[method+'Comparison']='AGREE'
            elif result['status'] in ('OPTIMAL','UNSAT') and status in ('SAT','UNSAT'):
                row[method+'Comparison']='DISAGREE_STATUS'
            else:row[method+'Comparison']='UNRESOLVED'
        records.append(row)
    fields=['task','family','category','B','b','inputSha256','oracleStatus','oraclePrimary','oracleSecondary',
            'wallSec','checkedSizes','reason','formula','certificatePath','previousStatus','previousReason',
            'evidenceSource','ATLAS-BComparison','MacroATLASComparison']
    fields += ['atlasBStatus','atlasBObjectivePrimary','atlasBObjectiveSecondary',
               'macroStatus','macroObjectivePrimary','macroObjectiveSecondary']
    summary_dir=campaign/'summary';summary_dir.mkdir(exist_ok=True)
    with (summary_dir/'per-case.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(records)
    statuses=collections.Counter(r['oracleStatus'] for r in records)
    comparison={m:dict(collections.Counter(r[m+'Comparison'] for r in records)) for m in ('ATLAS-B','MacroATLAS')}
    certified=sum(r['oracleStatus'] in ('OPTIMAL','UNSAT') for r in records)
    both_agree=sum(r['ATLAS-BComparison']=='AGREE' and r['MacroATLASComparison']=='AGREE' for r in records)
    mismatches=[r['task'] for r in records if 'DISAGREE' in r['ATLAS-BComparison'] or 'DISAGREE' in r['MacroATLASComparison']]
    uncertified=[{'task':r['task'],'status':r['oracleStatus'],'reason':r['reason']}
                 for r in records if r['oracleStatus'] not in ('OPTIMAL','UNSAT')]
    data={'expectedCases':623,'recordedCases':623-statuses.get('MISSING',0),'certifiedCases':certified,
          'statuses':dict(statuses),'comparison':comparison,'bothAgreeWithOracle':both_agree,
          'mismatches':mismatches,'uncertified':uncertified,
          'inheritedCertifiedCases':sum(r['evidenceSource']=='INHERITED' for r in records),
          'retriedUnresolvedCases':sum(bool(r['previousStatus']) and r['evidenceSource']=='CURRENT' and
                                        r['oracleStatus']!='MISSING' for r in records),
          'sumTaskWallSec':sum(float(r['wallSec']) for r in records if r['wallSec'] not in ('',None)),
          'campaignState':load(campaign/'state.json')}
    save(summary_dir/'summary.json',data)
    lines=['# RQ1 official 623: independent exact SMT oracle','',
           f"Recorded {data['recordedCases']}/623; independently certified {certified}/623.",
           f"Statuses: {dict(statuses)}",f"Sum of per-case wall time: {data['sumTaskWallSec']:.1f} s.",
           f"ATLAS-B comparison: {comparison['ATLAS-B']}",f"MacroATLAS comparison: {comparison['MacroATLAS']}",
           f"Both agree with certified oracle: {both_agree}.",f"Decisive disagreements: {len(mismatches)}.",
           '',f"Mismatching tasks: {mismatches}",
           '',f"Uncertified tasks and reasons: {uncertified}",
           '', 'Each OPTIMAL has a concrete Python-checked witness and SAT query at its size;',
           'every smaller exact size has a saved replayable SMT-LIB UNSAT query and record.',
           'Repair queries require retention of all listed old edges, proving the maximal',
           'primary objective by cardinality before minimizing rooted DAG size.',
           'TIMEOUT/UNKNOWN/MISSING are not counted as correctness agreements.']
    (summary_dir/'REPORT.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(data,ensure_ascii=False,indent=2))


def status(args):
    campaign=args.campaign.resolve();p=load(campaign/'plan.json')
    outcomes=collections.Counter()
    for case in p['cases']:
        path=job_dir(campaign,case)/'result.json'
        if path.exists():outcomes[load(path)['status']]+=1
    print(f"RQ1 exact 623: {sum(outcomes.values())}/623 | {dict(outcomes)} | state={load(campaign/'state.json')['status']}")


def main():
    parser=argparse.ArgumentParser()
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('plan')
    p.add_argument('--root',type=Path,default=DEFAULT_ROOT)
    p.add_argument('--table',type=Path,default=DEFAULT_TABLE)
    p.add_argument('--e4',type=Path,default=DEFAULT_E4)
    p.add_argument('--output',required=True,type=Path)
    p.add_argument('--max-size',type=int,default=18)
    p.add_argument('--case-timeout',type=int,default=300)
    p.add_argument('--solver-timeout',type=int,default=120)
    p.add_argument('--memory-gib',type=int,default=5)
    p=sub.add_parser('worker');p.add_argument('--campaign',required=True,type=Path);p.add_argument('--id',required=True)
    p=sub.add_parser('run');p.add_argument('--campaign',required=True,type=Path)
    p.add_argument('--workers',type=int,default=7);p.add_argument('--cpus',type=lambda s:[int(x) for x in s.split(',')],default=[2,4,6,8,10,12,14])
    p=sub.add_parser('status');p.add_argument('--campaign',required=True,type=Path)
    p=sub.add_parser('summary');p.add_argument('--campaign',required=True,type=Path)
    args=parser.parse_args()
    if args.command=='plan':plan(args)
    elif args.command=='worker':worker(args)
    elif args.command=='run':run(args)
    elif args.command=='status':status(args)
    else:summarize(args.campaign.resolve())


if __name__=='__main__':main()
