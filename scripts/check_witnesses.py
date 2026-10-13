#!/usr/bin/env python3
"""Check archived small SMT queries and witnesses without running SMT solving."""
import csv
import gzip
import hashlib
import json
from pathlib import Path
import sys
import tarfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'baselines/oracle'))
import z3
from rq1_exact_smt import parse_task,evaluate_witness


def main():
    assert z3.get_version_string()=='4.14.1','Install requirements.txt (Z3 4.14.1).'
    with tarfile.open(ROOT/'results/evidence/oracle/small_smt_evidence.tar.gz') as tar:
        files={m.name:tar.extractfile(m).read() for m in tar if m.isfile()}
    manifest=list(csv.DictReader((ROOT/'datasets/small/manifest.csv').open()))
    tasks={r['caseId']:parse_task(ROOT/'datasets/small'/r['task'],int(r['B']),int(r['b']),r['category']) for r in manifest}
    checks=sat=0
    for name,data in files.items():
        if not name.endswith('/record.json'):continue
        record=json.loads(data);folder=name.rsplit('/',1)[0]
        query=gzip.decompress(files[folder+'/query.smt2.gz'])
        assert hashlib.sha256(query).hexdigest()==record['querySha256']
        checks+=1
        if record['status']=='sat':
            witness=files[folder+'/witness.json']
            assert hashlib.sha256(witness).hexdigest()==record['witnessSha256']
            case_id=name.split('/')[1]
            assert evaluate_witness(tasks[case_id],json.loads(witness))
            sat+=1
    assert sat==819
    assert sum(n.endswith('/result.json') for n in files)==1000
    print(f'PASS: {checks} SMT query hashes, {sat} independently checked SAT witnesses, 1000 final results.')
    print('UNSAT results remain archived solver evidence; this command does not replay their SMT queries.')


if __name__=='__main__':main()
