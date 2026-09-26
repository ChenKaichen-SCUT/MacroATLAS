#!/usr/bin/env python3
"""Read-only audit of every frozen RQ1 tiny recheck SAT/UNSAT certificate."""

from __future__ import annotations

import argparse
import collections
import gzip
import hashlib
import json
from pathlib import Path

from rq1_exact_smt import evaluate_witness, parse_task


def read(path: Path):return json.loads(path.read_text())
def digest(data: bytes):return hashlib.sha256(data).hexdigest()


def audit(root: Path) -> dict:
    plan=read(root/'plan.json')
    cases=read(root/'dataset.json')['cases']
    if len(cases)!=1000 or digest((root/'dataset.json').read_bytes())!=plan['datasetSha256']:
        raise ValueError('Frozen dataset manifest mismatch')
    legacy={x['caseId']:x for x in map(json.loads,(root/'legacy.jsonl').read_text().splitlines())}
    counters=collections.Counter();bad=[]
    for row in cases:
        cid=row['id']
        try:
            task=parse_task(root/'inputs'/row['task'],row['B'],row['b'],'tiny_'+row['family'])
            assert task.source_sha256==row['inputSha256']
            result=read(root/'jobs'/cid/'result.json')
            assert result['inputSha256']==row['inputSha256'] and result['caseId']==cid
            assert result['status'] in ('SAT','UNSAT')
            steps=result['steps']
            expected_kept=(1,0) if row['family']=='repair' else (0,)
            positions={kept:[] for kept in expected_kept}
            for step in steps:
                kept,size=step['keptAtLeast'],step['size']
                assert kept in positions
                assert size==len(positions[kept])+1
                positions[kept].append(step['status'])
                folder=root/'jobs'/cid/f'kept_{kept}'/f'size_{size:02d}'
                record=read(folder/'record.json')
                assert all(record[key]==step[key] for key in ('status','size','keptAtLeast','querySha256'))
                query=gzip.decompress((folder/'query.smt2.gz').read_bytes())
                assert digest(query)==record['querySha256']
                assert record['status'] in ('sat','unsat')
                if record['status']=='sat':
                    witness=read(folder/'witness.json')
                    assert digest((folder/'witness.json').read_bytes())==record['witnessSha256']
                    assert evaluate_witness(task,witness)
                counters['queries']+=1
                counters[record['status']+'Queries']+=1
            if result['status']=='SAT':
                primary=result['objectivePrimary'];secondary=result['objectiveSecondary']
                assert primary in expected_kept
                assert positions[primary]==['unsat']*(secondary-1)+['sat']
                if row['family']=='repair' and primary==0:
                    assert positions[1]==['unsat']*task.B
                elif row['family']=='repair':assert not positions[0]
                witness=result['witness']
                assert witness['size']==secondary and witness.get('keptEdges',0)==primary
                assert evaluate_witness(task,witness)
                counters['verifiedOracleSat']+=1
            else:
                assert all(positions[kept]==['unsat']*task.B for kept in expected_kept)
            for method in ('atlas-b','macro'):
                old=legacy[cid]['methods'][method]
                if old['record']['status']=='SAT':
                    from rq1_tiny_corrected_recheck import verify_archived_formula
                    assert verify_archived_formula(task,old['formula'],old['record'])
                    counters[method+'VerifiedSat']+=1
            counters['auditedCases']+=1
            counters[result['status']]+=1
        except Exception as error:
            bad.append({'caseId':cid,'error':f'{type(error).__name__}: {error}'})
    return {'expectedCases':1000,**dict(counters),'bad':bad,
        'note':'Every stored SMT-LIB query hash and result sequence checked; Z3 UNSAT replies are not re-solved by this audit.'}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--campaign',type=Path,required=True)
    args=parser.parse_args();result=audit(args.campaign.resolve())
    print(json.dumps(result,indent=2,ensure_ascii=False))
    if result['bad']:raise SystemExit(1)
