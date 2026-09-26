#!/usr/bin/env python3
"""Read-only structural audit of a frozen RQ1 exact campaign's evidence."""

from __future__ import annotations

import argparse
import collections
import gzip
import hashlib
import json
from pathlib import Path

from rq1_exact_smt import evaluate_witness, parse_task


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read(path: Path):
    return json.loads(path.read_text())


def audit(campaign: Path) -> dict:
    plan=read(campaign/'plan.json')
    expected=(campaign/'plan.sha256').read_text().split()[0]
    if digest((campaign/'plan.json').read_bytes())!=expected:
        raise ValueError('Frozen plan hash mismatch')
    for name,key in [('rq1_exact_smt.py','encodingSha256'),
                     ('rq1_exact_campaign.py','controllerSha256')]:
        if digest((campaign/'code'/name).read_bytes())!=plan[key]:
            raise ValueError('Frozen '+name+' hash mismatch')
    outcomes=collections.Counter()
    bad=[]
    for case in plan['cases']:
        name=case['task'];job=campaign/'jobs'/case['id'];path=job/'result.json'
        if not path.exists():
            outcomes['MISSING']+=1
            continue
        result=read(path);outcomes[result['status']]+=1
        try:
            task=parse_task(campaign/'inputs'/name,int(case['B']),int(case['b']),case['category'])
            assert task.source_sha256==case['inputSha256']
            assert result['task']==name and result['caseId']==case['id']
            steps=result.get('steps',[])
            for index,step in enumerate(steps,1):
                assert step['size']==index
                folder=job/f'size_{index:03d}'
                record=read(folder/'record.json')
                assert record['size']==index and record['status']==step['status']
                query=gzip.decompress((folder/'query.smt2.gz').read_bytes())
                assert digest(query)==record['querySha256']==step['querySha256']
                if step['status']=='sat':
                    witness=read(folder/'witness.json')
                    assert digest((folder/'witness.json').read_bytes())==record['witnessSha256']
                    assert evaluate_witness(task,witness)
            if result['status']=='OPTIMAL':
                assert steps and steps[-1]['status']=='sat'
                assert all(step['status']=='unsat' for step in steps[:-1])
                assert len(steps)==result['objectiveSecondary']
                assert result['objectiveSecondary']<=task.B
                assert result['witness']==read(job/f'size_{len(steps):03d}'/'witness.json')
                assert evaluate_witness(task,result['witness'])
                if task.category=='repair':
                    maximum=5 if 'G0' in task.custom else 4
                    assert result['objectivePrimary']==maximum
                    assert result['witness']['keptEdges']==maximum
                else:
                    assert result['objectivePrimary']==0
            elif result['status']=='UNSAT':
                assert task.category!='repair'
                assert len(steps)==task.B<=plan['maxEncodedSize']
                assert all(step['status']=='unsat' for step in steps)
            elif result['status'] in ('UNKNOWN','TIMEOUT','ERROR'):
                pass
            else:
                raise AssertionError('Invalid status')
        except Exception as error:
            bad.append({'task':name,'error':f'{type(error).__name__}: {error}'})
    return {'expectedCases':len(plan['cases']),'recordedCases':sum(outcomes.values())-outcomes['MISSING'],
            'statuses':dict(outcomes),'structurallyAuditedCases':sum(outcomes.values())-outcomes['MISSING']-len(bad),
            'bad':bad,'replayNote':'UNSAT solver answers are structurally checked, not re-solved here; replay saved SMT-LIB for independent checking.'}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--campaign',required=True,type=Path)
    args=parser.parse_args()
    result=audit(args.campaign.resolve())
    print(json.dumps(result,indent=2,ensure_ascii=False))
    if result['bad']:
        raise SystemExit(1)
