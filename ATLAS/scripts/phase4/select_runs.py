#!/usr/bin/env python3
"""Make an explicit new preparation root for pre-registered common-solved/stratified repeats."""
import argparse
import csv
import json
import pathlib
import random
import shutil
import subprocess
from common import ATLAS, java_command, save_json, sha256
from validate_results import validate
from common import is_solved


def select(batch, root, output, mode, per_family, seed, b):
    rows,manifest=validate(batch)
    if output.exists():raise ValueError("New output directory required")
    output.mkdir(parents=True)
    groups={}
    for r in rows:groups.setdefault(r['task'],[]).append(r)
    eligible=[t for t,rs in groups.items() if mode!='common' or (len({r['variant'] for r in rs})==2 and all(is_solved(r) for r in rs))]
    selected=[];rng=random.Random(seed)
    for family in sorted({t.split('/')[0] for t in eligible}):
        names=sorted(t for t in eligible if t.split('/')[0]==family);rng.shuffle(names)
        selected+=names if mode=='common' else names[:per_family]
    for name in sorted(selected):
        src=(root/name).resolve();src.relative_to(root.resolve());dst=output/'inputs'/name;dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(src,dst)
        if src.with_suffix('.json').exists():shutil.copy2(src.with_suffix('.json'),dst.with_suffix('.json'))
    save_json(output/'selection.json',dict(mode=mode,seed=seed,sourceBatch=str(batch),sourceCommit=manifest['commit'],
                                         tasks=sorted(selected),sourceRawSha256=sha256(batch/'raw.csv'),
                                         note='Selection is reported separately; full-workload PAR-2 is not recomputed on this subset'))
    subprocess.run(java_command()+['--mode','coverage','--root',str((output/'inputs').resolve()),'--b',str(b),
                                   '--output',str((output/'analysis').resolve())],cwd=ATLAS,check=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('batch',type=pathlib.Path);p.add_argument('--root',type=pathlib.Path,required=True)
    p.add_argument('--output',type=pathlib.Path,required=True);p.add_argument('--mode',choices=['common','stratified'],default='common')
    p.add_argument('--per-family',type=int,default=10);p.add_argument('--seed',type=int,default=20260925);p.add_argument('--b',type=int,default=2)
    a=p.parse_args();select(a.batch,a.root,a.output,a.mode,a.per_family,a.seed,a.b)
