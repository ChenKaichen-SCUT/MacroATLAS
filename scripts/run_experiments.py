#!/usr/bin/env python3
"""Portable serial replay of the frozen inputs. New runs never overwrite evidence.

Each observation starts a fresh process. On timeout the entire process group,
including the native MaxSAT solver, is killed. A failed or censored run never
receives a completed-runtime value for PAR-2. Use Linux or the Docker image.
"""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'baselines/oracle'))
MANIFESTS={'benchmark':'benchmark/manifest.csv','small':'small/manifest.csv',
           'unary':'unary/manifest.csv','binary':'discussion/binary_manifest.csv',
           'profile':'discussion/profile_manifest.csv'}
NAMES={'atlas-b':'ATLAS-B','macro':'MacroATLAS'}


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n')


def load(path):
    return json.loads(path.read_text()) if path.exists() else {}


def execute(command,directory,timeout):
    directory.mkdir(parents=True,exist_ok=True)
    with (directory/'stdout.txt').open('w') as out, (directory/'stderr.txt').open('w') as err:
        start=time.monotonic()
        p=subprocess.Popen(command,cwd=ROOT,stdout=out,stderr=err,start_new_session=True)
        try:
            code=p.wait(timeout=timeout); status='OK' if code==0 else 'ERROR'
        except subprocess.TimeoutExpired:
            status='TIMEOUT'
        finally:
            try: os.killpg(p.pid,signal.SIGKILL)
            except ProcessLookupError: pass
            p.wait()
    return status,time.monotonic()-start


def java_base(args):
    # Count available processors consistently; CPU affinity is explicit and logged.
    prefix=['taskset','-c',args.cpu] if args.cpu else []
    return prefix+['java','-XX:ActiveProcessorCount=2','-Xms512m','-Xmx'+args.heap,
                   '-Djava.library.path='+str(ROOT/'lib')]


def learner(args,row,path,folder,method):
    cp=os.pathsep.join([str(ROOT/'target/classes'),str(ROOT/'lib/AlloyMax-1.0.3.jar'),
                        (ROOT/'target/runtime-classpath.txt').read_text().strip()])
    entry=java_base(args)+['-cp',cp,'cmu.s3d.ltl.experiment.ExperimentMain']
    common=['--file',str(path),'--output',str(folder),'--B',row['B'],'--b',row['b']]
    if args.kind=='translation':
        state,wall=execute(entry+['--mode','emit-scope','--variant',method,'--scope',row['scope']]+common,folder/'emission',120)
        if state!='OK':return dict(status='EMIT_'+state,totalSec=wall)
        command=java_base(args)+['-Djava.io.tmpdir='+str(folder),'-cp',cp,'Rq2Translate',str(folder/'model.als')]
        state,seconds=execute(command,folder/'translation',180)
        if state!='OK':return dict(status='TRANSLATION_'+state,totalSec=wall+seconds)
        data=json.loads((folder/'translation/stdout.txt').read_text().strip())
        assert data['solverInvoked'] is False and data['status']=='TRANSLATED_ONLY'
        data['totalSec']=wall+seconds
        return data
    state,wall=execute(entry+['--mode',method]+common,folder,180)
    data=load(folder/'metadata.json')
    if state!='OK':data['status']=state
    status=data.get('status','ERROR')
    data.update(totalSec=wall,par2Sec=wall if status in {'SAT','UNSAT'} else 360,
                verification=load(folder/'verification.json').get('status','NOT_RUN'))
    if status=='SAT' and data['verification']!='PASSED':
        raise AssertionError('SAT output did not pass verification: '+str(folder))
    return data


def oracle_worker(args):
    """Ascending exact sizes prove minimality; repair priorities remain lexicographic."""
    from rq1_exact_smt import parse_task,check_size
    import z3
    if z3.get_version_string() != '4.14.1':
        raise RuntimeError('This artifact requires Z3 4.14.1; install requirements.txt.')
    if args.oracle_memory_gib:
        import resource
        cap=int(args.oracle_memory_gib*1024**3)
        resource.setrlimit(resource.RLIMIT_AS,(cap,cap))
    row=json.loads(args.row)
    task=parse_task(Path(args.input),int(row['B']),int(row['b']),row['category'])
    assert task.source_sha256==row['input_sha256']
    folder=Path(args.output);begin=time.monotonic();steps=[];final=None
    tiny=row['category'].startswith('tiny_')
    repair=row['category'] in {'repair','tiny_repair'}
    priorities=(1,0) if row['category']=='tiny_repair' else ((5 if 'G0' in task.custom else 4),) if repair else (0,)
    for kept in priorities:
        for size in range(1,task.B+1):
            seconds=args.oracle_query_seconds
            if not tiny:seconds=min(seconds,4500-(time.monotonic()-begin)-1)
            if seconds<=0:final=dict(status='TIMEOUT',reason='CASE_DEADLINE');break
            dest=folder/f'kept_{kept}'/f'size_{size:03d}'
            record=check_size(task,size,dest,int(seconds*1000),kept);steps.append(record)
            if record['status']=='sat':
                witness=load(dest/'witness.json')
                final=dict(status='SAT' if tiny else 'OPTIMAL',objectivePrimary=witness.get('keptEdges',0),objectiveSecondary=size,verification='PASSED')
                break
            if record['status']=='unknown':
                final=dict(status='TIMEOUT' if 'timeout' in record['reasonUnknown'].lower() else 'UNKNOWN',reason=record['reasonUnknown']);break
        if final:break
    # Failure at maximum repair retention does not establish infeasibility at lower retention.
    if final is None:
        final=dict(status='UNKNOWN',reason='REPAIR_MAX_KEPT_NOT_FOUND') if repair and not tiny else dict(status='UNSAT')
    final.update(task=row['task'],totalSec=time.monotonic()-begin,z3Version=z3.get_version_string(),steps=steps)
    save(folder/'result.json',final)


def main(args):
    if os.name!='posix':raise SystemExit('Run inside Linux or the supplied Docker image.')
    if args.kind=='translation' and args.suite!='benchmark':raise SystemExit('Translation uses only the frozen benchmark scopes.')
    if args.kind=='oracle' and args.suite not in {'benchmark','small'}:raise SystemExit('Oracle suites: benchmark, small.')
    if args.limit is not None and args.limit<1:raise SystemExit('--limit must be positive')
    manifest=ROOT/'datasets'/MANIFESTS[args.suite]
    with manifest.open() as f: data=list(csv.DictReader(f))
    if args.task:
        data=[r for r in data if r['task']==args.task]
        if len(data)!=1:raise SystemExit('Task must match exactly one manifest entry.')
    if args.limit:data=data[:args.limit]
    output=Path(args.output).resolve();output.mkdir(parents=True,exist_ok=False)
    methods=args.methods.split(',')
    if any(m not in NAMES for m in methods):raise SystemExit('Methods: atlas-b,macro')
    if args.suite=='profile':methods=['macro']
    if args.kind=='oracle':methods=['oracle']
    query_seconds=args.oracle_query_seconds or (30 if args.suite=='small' else 1500)
    config=vars(args).copy();config.update(cases=len(data),methods=methods,oracle_query_seconds=query_seconds,
                                       runTimeoutSec=180,emitTimeoutSec=120,translationTimeoutSec=180,
                                       replay=True,manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest())
    config['java']=subprocess.run(['java','-version'],capture_output=True,text=True).stderr.strip()
    save(output/'configuration.json',config)
    observations=[]
    for row in data:
        path=manifest.parent/row['task'];assert hashlib.sha256(path.read_bytes()).hexdigest()==row['input_sha256']
        for method in methods:
            folder=output/'jobs'/row['task'].removesuffix('.trace')/method
            if args.kind=='oracle':
                command=[sys.executable,str(Path(__file__).resolve()),'--worker','--row',json.dumps(row),
                         '--input',str(path),'--output',str(folder),'--oracle-query-seconds',str(query_seconds),
                         '--oracle-memory-gib',str(args.oracle_memory_gib)]
                deadline=max(60,2*int(row['B'])*(query_seconds+5)) if args.suite=='small' else 4500
                state,wall=execute(command,folder,deadline)
                result=load(folder/'result.json')
                if state!='OK':result=dict(status=state,totalSec=wall)
            else:result=learner(args,row,path,folder,method)
            record={**result,'task':row['task'],'algorithm':NAMES.get(method,'SMT Oracle'),
                    'B':row['B'],'b':row['b'],'inputSha256':row['input_sha256']}
            save(folder/'replay.json',record)
            observations.append({k:v for k,v in record.items() if isinstance(v,(str,int,float,bool))})
            print(f"{len(observations)} {row['task']} {method} {result['status']} {result['totalSec']:.3f}s",flush=True)
    keys=list(dict.fromkeys(k for r in observations for k in r))
    with (output/'observations.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=keys,lineterminator='\n');writer.writeheader();writer.writerows(observations)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--suite',choices=MANIFESTS,default='benchmark')
    p.add_argument('--kind',choices=['solving','translation','oracle'],default='solving')
    p.add_argument('--output',required=True)
    p.add_argument('--methods',default='atlas-b,macro')
    p.add_argument('--limit',type=int);p.add_argument('--task')
    p.add_argument('--heap',default='4g');p.add_argument('--cpu')
    p.add_argument('--oracle-query-seconds',type=float)
    p.add_argument('--oracle-memory-gib',type=float,default=5)
    p.add_argument('--worker',action='store_true',help=argparse.SUPPRESS)
    p.add_argument('--row',help=argparse.SUPPRESS);p.add_argument('--input',help=argparse.SUPPRESS)
    args=p.parse_args()
    if args.worker:oracle_worker(args)
    else:main(args)
