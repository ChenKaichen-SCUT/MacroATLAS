#!/usr/bin/env python3
"""Verify the paper's Zenodo archive and derive historical workload/runtime provenance."""
import argparse
import csv
import hashlib
import pathlib
import urllib.request
import zipfile
from common import ATLAS, sha256, save_json

URL="https://zenodo.org/records/14578202/files/ATLAS-main.zip?download=1"
MD5="d60fecbcdf54d47a9c00a791865365bd"


def audit(archive, output):
    if not archive.exists():
        archive.parent.mkdir(parents=True,exist_ok=True)
        urllib.request.urlretrieve(URL,archive)
    assert hashlib.md5(archive.read_bytes()).hexdigest()==MD5,"Artifact checksum differs from Zenodo record"
    same=[];differences=[]
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            if name.endswith('/') or '/benchmark/' not in name:continue
            relative=name.split('/benchmark/',1)[1]
            local=ATLAS/'benchmark'/relative
            if local.exists() and local.read_bytes()==z.read(name):same.append(relative)
            else:differences.append(relative)
    tables=[]
    for name in ["baselines/baseline_alloy_all.csv","peterson/peterson_alloy.csv","voting/voting_alloy.csv",
                 "robot/robot_alloy.csv","weakening/weakening_alloy_gr1_new.csv"]:
        with (ATLAS/'benchmark_results'/name).open() as f:rows=list(csv.DictReader(f))
        seconds=[]
        for row in rows:
            try:seconds.append(float(row['solvingTime']))
            except ValueError:seconds.append(180.)
        tables.append(dict(table=name,rows=len(rows),historicalCappedHours=sum(seconds)/3600,
                           sha256=sha256(ATLAS/'benchmark_results'/name)))
    result=dict(artifactUrl=URL,archiveMd5=MD5,archiveSha256=sha256(archive),
                matchingBenchmarkFiles=len(same),differences=differences,historicalTables=tables,
                warning="Archived runtime is provenance and planning evidence, never current-machine baseline")
    save_json(output,result)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--archive',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True)
    a=p.parse_args();print(audit(a.archive,a.output))
