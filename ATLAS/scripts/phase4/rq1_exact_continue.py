#!/usr/bin/env python3
"""Preserve certified RQ1 jobs and retry only unresolved cases with a new plan."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import shutil

from rq1_exact_audit import audit


def read(path: Path):
    return json.loads(path.read_text())


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(previous: Path, current: Path):
    old,new=read(previous/'plan.json'),read(current/'plan.json')
    keys=('task','B','b','category','inputSha256')
    if [tuple(c[k] for k in keys) for c in old['cases']] != [
       tuple(c[k] for k in keys) for c in new['cases']]:
        raise ValueError('The two plans are not the same 623 frozen cases')
    if new['caseTimeoutSec']<=old['caseTimeoutSec'] or new['solverTimeoutSec']<=old['solverTimeoutSec']:
        raise ValueError('Continuation limits must be longer')
    check=audit(previous)
    if check['bad']:
        raise ValueError(f'Old campaign evidence failed audit: {check["bad"][:3]}')
    if (current/'jobs').exists() or (current/'continuation.json').exists():
        raise ValueError('Destination campaign already contains jobs or continuation metadata')
    history=[];inherited=[]
    for case in old['cases']:
        source=previous/'jobs'/case['id']
        if not source.exists():
            continue
        result_path=source/'result.json'
        result=read(result_path) if result_path.exists() else {}
        status=result.get('status','INTERRUPTED')
        history.append({'task':case['task'],'caseId':case['id'],'previousStatus':status,
                        'previousReason':result.get('reason',''),'previousWallSec':result.get('wallSec',''),
                        'previousJobPath':str(source)})
        if status in ('OPTIMAL','UNSAT'):
            target=current/'jobs'/case['id']
            shutil.copytree(source,target)
            (target/'inherited-from.json').write_text(json.dumps({
                'previousPlanSha256':sha(previous/'plan.json'),
                'previousEncodingSha256':old['encodingSha256'],
                'previousControllerSha256':old['controllerSha256'],
                'previousJobPath':str(source),
                'resultSha256':sha(result_path)},indent=2)+'\n')
            inherited.append(case['task'])
    with (current/'previous-attempts.csv').open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=['task','caseId','previousStatus','previousReason',
                                                   'previousWallSec','previousJobPath'])
        writer.writeheader();writer.writerows(history)
    metadata={'previousCampaign':str(previous),'previousPlanSha256':sha(previous/'plan.json'),
              'currentPlanSha256':sha(current/'plan.json'),
              'previousLimits':{'solverTimeoutSec':old['solverTimeoutSec'],'caseTimeoutSec':old['caseTimeoutSec']},
              'currentLimits':{'solverTimeoutSec':new['solverTimeoutSec'],'caseTimeoutSec':new['caseTimeoutSec']},
              'previousRecordedAttempts':len(history),'inheritedCertifiedCases':len(inherited),
              'inheritedTasks':inherited,'policy':'Only OPTIMAL/UNSAT jobs are inherited; all other jobs are retried'}
    (current/'continuation.json').write_text(json.dumps(metadata,indent=2)+'\n')
    (current/'state.json').write_text(json.dumps({'status':'READY_CONTINUATION',
                                                  'inheritedCertifiedCases':len(inherited)},indent=2)+'\n')
    print(f'Inherited {len(inherited)} certified cases; {623-len(inherited)} remain to attempt')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--previous',type=Path,required=True)
    parser.add_argument('--campaign',type=Path,required=True)
    args=parser.parse_args()
    main(args.previous.resolve(),args.campaign.resolve())
