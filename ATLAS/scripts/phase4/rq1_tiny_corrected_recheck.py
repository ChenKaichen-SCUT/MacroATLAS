#!/usr/bin/env python3
"""Recheck the frozen 1,000 tiny RQ1 inputs with the corrected independent SMT oracle.

Reads input bytes and prior results from the archived experiment; never calls
the generator or either learning algorithm. Every SAT formula is checked by the
concrete, non-SMT verifier in rq1_exact_smt.py.
"""

from __future__ import annotations

import argparse
import collections
import concurrent.futures
import csv
import hashlib
import json
from pathlib import Path
import re
import tarfile
import time

import z3

from rq1_exact_smt import BINARY, TINY_CUSTOM_TEXT, UNARY, check_size, evaluate_witness, parse_task


ATLAS=Path(__file__).resolve().parents[2]
ARCHIVE=ATLAS/'experiment_artifacts/2026-09-23/archives/rq1-tiny-primary-1000.tar.gz'
LOCAL_DATASET=ATLAS/'experiment_artifacts/2026-09-23/rq1-tiny/dataset.json'
PREFIX='rq1-tiny-primary-1000/'
FAMILIES=('plain','nnf','cnf','dnf','required','no_dag_reuse','global_prop','repair')


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save(path: Path, value) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    temp.replace(path)


def read(path: Path):
    return json.loads(path.read_text())


def prepare(output: Path):
    if output.exists():raise ValueError('Output must be a new directory')
    output.mkdir(parents=True)
    with tarfile.open(ARCHIVE) as tar:
        frozen=tar.extractfile(PREFIX+'dataset.json').read()
        if sha(frozen)!=sha(LOCAL_DATASET.read_bytes()):
            raise ValueError('Archived and local frozen manifests differ')
        dataset=json.loads(frozen)
        cases=dataset['cases']
        if len(cases)!=1000 or len({row['id'] for row in cases})!=1000:
            raise ValueError('Expected 1,000 unique frozen cases')
        if collections.Counter(row['family'] for row in cases)!={name:125 for name in FAMILIES}:
            raise ValueError('Expected eight frozen families of 125 cases')
        wanted={PREFIX+'inputs/'+row['task']:row for row in cases}
        historical={}
        for member in tar:
            if not member.isfile():continue
            name=member.name
            if name in wanted:
                row=wanted.pop(name)
                data=tar.extractfile(member).read()
                if sha(data)!=row['inputSha256']:
                    raise ValueError('Frozen input SHA mismatch: '+row['id'])
                path=output/'inputs'/row['task']
                path.parent.mkdir(parents=True,exist_ok=True)
                path.write_bytes(data)
                task=parse_task(path,row['B'],row['b'],'tiny_'+row['family'])
                if task.source_sha256!=row['inputSha256']:
                    raise ValueError('Parser changed frozen input identity')
                continue
            parts=name.split('/')
            if len(parts)!=5 or parts[1]!='jobs' or parts[3] not in ('oracle','atlas-b','macro'):
                continue
            key=(parts[2],parts[3])
            if parts[4]=='record.json':historical.setdefault(key,{})['record']=json.load(tar.extractfile(member))
            elif parts[4]=='reconstructed_formula.txt':
                historical.setdefault(key,{})['formula']=tar.extractfile(member).read().decode().strip()
        if wanted:raise ValueError(f'{len(wanted)} frozen inputs missing')
    for row in cases:
        for method in ('oracle','atlas-b','macro'):
            item=historical.get((row['id'],method),{})
            record=item.get('record')
            if record is None or record['inputSha256']!=row['inputSha256'] or record['caseId']!=row['id']:
                raise ValueError('Missing/misaligned archived method record: '+row['id']+' '+method)
            if record['status']=='SAT' and method!='oracle' and not item.get('formula'):
                raise ValueError('Archived SAT formula missing: '+row['id']+' '+method)
    (output/'dataset.json').write_bytes(frozen)
    with (output/'legacy.jsonl').open('w') as handle:
        for row in cases:
            entry={'caseId':row['id'],'inputSha256':row['inputSha256'],
                   'methods':{m:historical[(row['id'],m)] for m in ('oracle','atlas-b','macro')}}
            handle.write(json.dumps(entry,ensure_ascii=False)+'\n')
    save(output/'plan.json',{'archive':str(ARCHIVE.relative_to(ATLAS.parent)),
        'archiveSha256':sha(ARCHIVE.read_bytes()),'datasetSha256':sha(frozen),
        'encodingSha256':sha(Path(__file__).with_name('rq1_exact_smt.py').read_bytes()),
        'controllerSha256':sha(Path(__file__).read_bytes()),'z3Version':z3.get_version_string(),
        'expectedCases':1000,'families':{x:125 for x in FAMILIES},
        'weakeningCases':0,'childrenOfSemantics':'n.^(l+r), all strict descendants',
        'objective':'maximize kept old edges, then minimize rooted DAG size for repair; otherwise minimum rooted DAG size'})
    print('Prepared exactly 1,000 SHA-checked frozen inputs; no instance was generated')


def check_plan(output: Path):
    plan=read(output/'plan.json')
    if sha(ARCHIVE.read_bytes())!=plan['archiveSha256'] or sha((output/'dataset.json').read_bytes())!=plan['datasetSha256']:
        raise ValueError('Frozen source archive/manifest changed')
    if sha(Path(__file__).with_name('rq1_exact_smt.py').read_bytes())!=plan['encodingSha256']:
        raise ValueError('Oracle implementation changed during campaign')
    if sha(Path(__file__).read_bytes())!=plan['controllerSha256'] or z3.get_version_string()!=plan['z3Version']:
        raise ValueError('Controller or solver changed during campaign')
    return read(output/'dataset.json')['cases']


def run_case(output_name: str, row: dict, timeout_ms: int) -> dict:
    output=Path(output_name)
    path=output/'inputs'/row['task']
    task=parse_task(path,row['B'],row['b'],'tiny_'+row['family'])
    if task.source_sha256!=row['inputSha256']:raise ValueError('Frozen input changed: '+row['id'])
    job=output/'jobs'/row['id'];result_path=job/'result.json'
    if result_path.exists():return read(result_path)
    job.mkdir(parents=True,exist_ok=True)
    begin=time.monotonic();steps=[];final=None
    targets=(1,0) if row['family']=='repair' else (0,)
    for kept in targets:
        for size in range(1,task.B+1):
            record=check_size(task,size,job/f'kept_{kept}'/f'size_{size:02d}',timeout_ms,kept)
            steps.append({'keptAtLeast':kept,**record})
            if record['status']=='sat':
                witness=read(job/f'kept_{kept}'/f'size_{size:02d}'/'witness.json')
                final={'status':'SAT','objectivePrimary':witness.get('keptEdges',0),
                       'objectiveSecondary':size,'witness':witness,'verification':'PASSED'}
                break
            if record['status']=='unknown':
                final={'status':'UNKNOWN','reason':record['reasonUnknown'],'verification':'NOT_APPLICABLE'}
                break
        if final:break
    if final is None:final={'status':'UNSAT','objectivePrimary':0,'objectiveSecondary':0,
                            'verification':'NOT_APPLICABLE'}
    final.update(caseId=row['id'],family=row['family'],task=row['task'],inputSha256=row['inputSha256'],
                 steps=steps,wallSec=time.monotonic()-begin,z3Version=z3.get_version_string())
    save(result_path,final)
    return final


def run(output: Path,workers: int,timeout_ms: int):
    cases=check_plan(output)
    if workers<1 or timeout_ms<1:raise ValueError('Invalid workers/timeout')
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
        futures={executor.submit(run_case,str(output),row,timeout_ms):row['id'] for row in cases}
        done=0
        for future in concurrent.futures.as_completed(futures):
            result=future.result();done+=1
            if done%25==0 or done==len(cases):
                print(f'{done}/{len(cases)} {result["caseId"]} {result["status"]}',flush=True)
    summarize(output)


def parse_formula(text: str) -> dict:
    tokens=re.findall(r'x[0-9]+|->|[!XFG&|(),]',text)
    if ''.join(tokens)!=re.sub(r'\s+','',text):raise ValueError('Unknown formula token: '+text)
    nodes=[];pos=0
    def parse():
        nonlocal pos
        if pos>=len(tokens):raise ValueError('Incomplete formula')
        label=tokens[pos];pos+=1
        if label.startswith('x'):
            idx=len(nodes);nodes.append({'id':idx,'label':label});return idx
        if label not in UNARY+BINARY or tokens[pos]!='(':
            raise ValueError('Invalid formula grammar')
        pos+=1;left=parse();right=None
        if label in BINARY:
            if tokens[pos]!=',':raise ValueError('Binary comma missing')
            pos+=1;right=parse()
        if tokens[pos]!=')':raise ValueError('Formula closing parenthesis missing')
        pos+=1;idx=len(nodes)
        node={'id':idx,'label':label,'left':left}
        if right is not None:node['right']=right
        nodes.append(node)
        return idx
    root=parse()
    if pos!=len(tokens) or root!=len(nodes)-1:raise ValueError('Formula trailing text')
    return {'nodes':nodes,'root':root,'size':len(nodes),
            'binaryNodes':sum(node['label'] in BINARY for node in nodes)}


def verify_archived_formula(task, formula: str, record: dict) -> bool:
    witness=parse_formula(formula)
    if witness['size']!=int(record['objectiveSecondary']):return False
    if task.category=='tiny_repair':
        x0=next((i for i,node in enumerate(witness['nodes']) if node['label']=='x0'),None)
        if x0 is None:return False
        witness['namedNodes']={'F0':witness['root'],'x0':x0}
        witness['keptEdges']=int(witness['nodes'][-1]['left']==x0)
        if witness['keptEdges']!=int(record['objectivePrimary']):return False
    return evaluate_witness(task,witness)


def summarize(output: Path):
    cases=check_plan(output)
    legacy={x['caseId']:x for x in map(json.loads,(output/'legacy.jsonl').read_text().splitlines())}
    detail=[];changes=[];family=collections.defaultdict(lambda:collections.Counter())
    for row in cases:
        cid=row['id'];task=parse_task(output/'inputs'/row['task'],row['B'],row['b'],'tiny_'+row['family'])
        path=output/'jobs'/cid/'result.json'
        if not path.exists():raise ValueError('Incomplete corrected run: '+cid)
        result=read(path);old=legacy[cid]['methods']
        if result['inputSha256']!=row['inputSha256'] or result['status'] not in ('SAT','UNSAT'):
            raise ValueError('Nondecisive or wrong-input Oracle result: '+cid)
        if result['status']=='SAT' and not evaluate_witness(task,result['witness']):
            raise ValueError('Corrected Oracle witness failed independent verifier: '+cid)
        verified={}
        for method in ('atlas-b','macro'):
            record=old[method]['record']
            if record['status'] not in ('SAT','UNSAT'):raise ValueError('Nondecisive old method result: '+cid)
            verified[method]=(record['status']=='SAT' and verify_archived_formula(task,old[method]['formula'],record))
            if record['status']=='SAT' and not verified[method]:
                raise ValueError('Archived SAT formula failed independent verifier: '+cid+' '+method)
        prev=old['oracle']['record']
        changed_status=prev['status']!=result['status']
        changed_objective=(result['status']=='SAT' and prev['status']=='SAT' and
            (int(prev['objectivePrimary']),int(prev['objectiveSecondary']))!=
            (result['objectivePrimary'],result['objectiveSecondary']))
        if changed_status or changed_objective:
            changes.append({'caseId':cid,'family':row['family'],'oldStatus':prev['status'],
                'oldPrimary':prev['objectivePrimary'],'oldSecondary':prev['objectiveSecondary'],
                'newStatus':result['status'],'newPrimary':result['objectivePrimary'],
                'newSecondary':result['objectiveSecondary'],
                'reason':'Corrected independent Oracle recomputation; inspect per-size SMT evidence'})
        def objective_mismatch(method):
            r=old[method]['record']
            return (r['status']=='SAT' and result['status']=='SAT' and
                    (int(r['objectivePrimary']),int(r['objectiveSecondary']))!=
                    (result['objectivePrimary'],result['objectiveSecondary']))
        f=family[row['family']];f['cases']+=1;f[result['status']]+=1
        f['oracleSatVerified']+=result['status']=='SAT'
        f['atlasBSatVerified']+=verified['atlas-b'];f['macroSatVerified']+=verified['macro']
        for m in ('atlas-b','macro'):
            f[m+'StatusDiff']+=old[m]['record']['status']!=result['status']
            f[m+'ObjectiveDiff']+=objective_mismatch(m)
        detail.append({'caseId':cid,'family':row['family'],'task':row['task'],'inputSha256':row['inputSha256'],
            'B':row['B'],'b':row['b'],'oracleStatus':result['status'],
            'oraclePrimary':result['objectivePrimary'],'oracleSecondary':result['objectiveSecondary'],
            'oracleSatVerified':result['status']=='SAT','oracleWallSec':result['wallSec'],
            'oldOracleStatus':prev['status'],'oldOraclePrimary':prev['objectivePrimary'],
            'oldOracleSecondary':prev['objectiveSecondary'],
            'atlasBStatus':old['atlas-b']['record']['status'],
            'atlasBPrimary':old['atlas-b']['record']['objectivePrimary'],
            'atlasBSecondary':old['atlas-b']['record']['objectiveSecondary'],
            'atlasBSatVerified':verified['atlas-b'],
            'macroStatus':old['macro']['record']['status'],
            'macroPrimary':old['macro']['record']['objectivePrimary'],
            'macroSecondary':old['macro']['record']['objectiveSecondary'],
            'macroSatVerified':verified['macro'],
            'macroStatusDiff':old['macro']['record']['status']!=result['status'],
            'macroObjectiveDiff':objective_mismatch('macro'),
            'atlasBStatusDiff':old['atlas-b']['record']['status']!=result['status'],
            'atlasBObjectiveDiff':objective_mismatch('atlas-b'),
            'oldOracleChanged':changed_status or changed_objective})
    summary={name:dict(family[name]) for name in FAMILIES}
    total=collections.Counter()
    for count in family.values():total.update(count)
    summary['TOTAL']=dict(total)
    output.joinpath('summary').mkdir(exist_ok=True)
    with (output/'summary/per-case.csv').open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(detail[0]),lineterminator='\n');writer.writeheader();writer.writerows(detail)
    with (output/'summary/changes.csv').open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=['caseId','family','oldStatus','oldPrimary','oldSecondary',
            'newStatus','newPrimary','newSecondary','reason'],lineterminator='\n')
        writer.writeheader();writer.writerows(changes)
    save(output/'summary/summary.json',{'families':summary,'oldOracleChanges':len(changes),
        'weakeningCases':0,'weakeningCorrectionImpact':'NOT_APPLICABLE: frozen eight-family dataset has no Weakening inputs',
        'sourceArchiveSha256':read(output/'plan.json')['archiveSha256'],
        'encodingSha256':read(output/'plan.json')['encodingSha256'],
        'statusAgreementDenominator':1000,'optimalObjectiveDenominator':total['SAT']})
    lines=['# 冻结的 1,000 个 RQ1 小规模实例：修正后独立 Oracle 完整复核','',
        '从原始归档复制并核对了全部 1,000 个输入 SHA-256；未重新生成实例。独立 Z3 有限 DAG 编码逐规模证明可满足性，SAT 见证与原 ATLAS-B / MacroATLAS 返回的公式都由具体 lasso/约束 verifier 重验。',
        'CNF/DNF 的 `childrenOf[n]` 按 `n.^(l+r)` 的**所有严格后代**检查。修正前后的 Weakening 代码对本批次不适用，因为八类中没有 Weakening 实例。','',
        '| family | 题数 | Oracle SAT | Oracle UNSAT | Macro 状态分歧 | Macro SAT 目标分歧 | Oracle SAT 验证 | Macro SAT 验证 |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for name in (*FAMILIES,'TOTAL'):
        x=summary[name]
        lines.append(f"| {name} | {x.get('cases',0)} | {x.get('SAT',0)} | {x.get('UNSAT',0)} | {x.get('macroStatusDiff',0)} | {x.get('macroObjectiveDiff',0)} | {x.get('oracleSatVerified',0)} | {x.get('macroSatVerified',0)} |")
    lines.extend(['',f"ATLAS-B：状态分歧 {total.get('atlas-bStatusDiff',0)}，SAT 最优目标分歧 {total.get('atlas-bObjectiveDiff',0)}，SAT 输出独立验证通过 {total.get('atlasBSatVerified',0)}。",
        f"旧 Oracle 与本次重新求解的状态/目标变化：**{len(changes)}**；逐题见 `changes.csv`。",
        f"状态一致率：{(1000-total.get('macroStatusDiff',0))/10:.1f}%；SAT 最优目标一致率：{(total['SAT']-total.get('macroObjectiveDiff',0))/total['SAT']*100:.1f}%。",
        '每题 SHA、完整字典序目标和三方验证见 `per-case.csv`；每个 Oracle SAT/UNSAT 查询及见证见 `../jobs/`。',
        '', '复现：`python3 ATLAS/scripts/phase4/rq1_tiny_corrected_recheck.py prepare --output <新目录>`，然后 `run --output <新目录> --workers 8`。'])
    (output/'summary/REPORT.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'families':summary,'oldOracleChanges':len(changes)},ensure_ascii=False,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    commands=parser.add_subparsers(dest='command',required=True)
    for command in ('prepare','run','summarize'):
        sub=commands.add_parser(command);sub.add_argument('--output',type=Path,required=True)
        if command=='run':
            sub.add_argument('--workers',type=int,default=8)
            sub.add_argument('--timeout-ms',type=int,default=30000)
    args=parser.parse_args();output=args.output.resolve()
    if args.command=='prepare':prepare(output)
    elif args.command=='run':run(output,args.workers,args.timeout_ms)
    else:summarize(output)
