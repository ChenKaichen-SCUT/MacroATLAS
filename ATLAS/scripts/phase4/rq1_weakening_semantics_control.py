#!/usr/bin/env python3
"""Reproduce the old/new strict-descendant Weakening negative control."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from rq1_exact_smt import ExactEncoding, evaluate_witness, parse_task


ATLAS=Path(__file__).resolve().parents[2]
BENCHMARK=ATLAS/'experiment_artifacts/2026-09-26/rq3-constraint-audit/inputs/weakening/weaken_antecedent/weaken_antecedent_10_10_10.trace'
OLD='12bb7e0c60058e7278f06977c05330adc9fe1e1e:ATLAS/scripts/phase4/rq1_exact_smt.py'
NODES=[{'id':0,'label':'x0'}, {'id':1,'label':'x1'},
       {'id':2,'label':'G','left':1},
       {'id':3,'label':'&','left':0,'right':2},
       {'id':4,'label':'->','left':3,'right':1},
       {'id':5,'label':'G','left':4}]
WITNESS={'nodes':NODES,'root':5,'size':6,'binaryNodes':2}


def pin(encoding):
    for node in NODES:
        i=node['id'];encoding.solver.add(encoding.kind_is(i,node['label']))
        if 'left' in node:encoding.solver.add(encoding.left[i]==node['left'])
        if 'right' in node:encoding.solver.add(encoding.right[i]==node['right'])
    return str(encoding.solver.check())


def run():
    current=parse_task(BENCHMARK,10,2,'weakening_b2')
    current=dataclasses.replace(current,positive=(),negative=())
    old_bytes=subprocess.check_output(['git','show',OLD],cwd=ATLAS.parent)
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'old_core.py';path.write_bytes(old_bytes)
        spec=importlib.util.spec_from_file_location('old_core',path)
        old=importlib.util.module_from_spec(spec)
        sys.modules['old_core']=old;spec.loader.exec_module(old)
        old_task=old.Task((),(),current.operators,current.ap,current.B,current.b,
                          current.category,current.custom,current.source_sha256)
        old_smt=pin(old.ExactEncoding(old_task,6))
        old_verify=old.evaluate_witness(old_task,WITNESS)
    new_smt=pin(ExactEncoding(current,6))
    new_verify=evaluate_witness(current,WITNESS)
    if (old_smt,old_verify,new_smt,new_verify)!=('sat',True,'unsat',False):
        raise AssertionError('Weakening old/new negative control changed')
    return {'benchmarkPath':str(BENCHMARK.relative_to(ATLAS.parent)),
            'benchmarkSha256':current.source_sha256,
            'constraintSha256':hashlib.sha256(current.custom.encode()).hexdigest(),
            'oldSource':OLD,'oldSourceSha256':hashlib.sha256(old_bytes).hexdigest(),
            'newSourceSha256':hashlib.sha256(Path(__file__).with_name('rq1_exact_smt.py').read_bytes()).hexdigest(),
            'removedExamplesForStructuralControl':True,
            'formula':'G(->(&(x0,G(x1)),x1))',
            'semanticReason':'G(x1) is a strict descendant of Imply0, although neither direct child of Imply0 is temporal',
            'oldSmt':old_smt,'oldVerifier':old_verify,'newSmt':new_smt,'newVerifier':new_verify,
            'frozenTinyWeakeningCases':0}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=run()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))
