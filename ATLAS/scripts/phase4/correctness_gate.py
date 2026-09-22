#!/usr/bin/env python3
"""Run the frozen regression/differential gates before accepting formal timing results."""
import argparse
import pathlib
import subprocess
import sys
import xml.etree.ElementTree as ET
from common import ATLAS, environment, save_json


def gate(output):
    env=environment()
    if env["dirty"]:
        raise ValueError("Commit implementation before issuing a formal correctness certificate")
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.with_suffix('.log').open('w') as log:
        subprocess.run(['mvn','-B','clean','verify','dependency:build-classpath','-Dmdep.outputFile=target/runtime-classpath.txt',
                        '-DincludeScope=runtime'],cwd=ATLAS,stdout=log,stderr=subprocess.STDOUT,check=True)
        subprocess.run([sys.executable,'-m','unittest','discover','-s','scripts/phase4','-p','test_*.py','-v'],
                       cwd=ATLAS,stdout=log,stderr=subprocess.STDOUT,check=True)
    tests=0
    for f in (ATLAS/'target/surefire-reports').glob('TEST-*.xml'):
        root=ET.parse(f).getroot();tests+=int(root.attrib['tests'])
        assert all(int(root.attrib[k])==0 for k in ['errors','failures','skipped'])
    assert tests>=94
    expected={'phase3-tiny-results.txt':'tasks=243','phase3-repair-results.txt':'tasks=50','phase4-matched-reference.txt':'tasks=80'}
    for name,line in expected.items():assert line in (ATLAS/'target'/name).read_text()
    tested=environment()
    assert not tested['dirty'] and all(tested[k]==env[k] for k in ['commit','java','alloySha256','solverSha256'])
    env=tested
    save_json(output,dict(env,junitTests=tests,status='PASSED',ordinaryTasks=243,repairTasks=50,matchedReferenceTasks=80))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=pathlib.Path,default=ATLAS/'generated/phase4-gate.json')
    a=p.parse_args();gate(a.output.resolve())
