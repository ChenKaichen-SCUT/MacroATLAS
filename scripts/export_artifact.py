#!/usr/bin/env python3
"""Validate and export the curated tree without Git history or local byproducts."""
import argparse
import gzip
import hashlib
import io
from pathlib import Path
import re
import tarfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
DIRS={'method','baselines','datasets','results','scripts','lib'}
FILES={'README.md','REPRODUCING.md','THIRD_PARTY.md','VALIDATION.md','Dockerfile',
       'pom.xml','requirements.txt','.gitignore','.dockerignore','.gitattributes'}
TEXT={'.md','.txt','.py','.kt','.java','.xml','.json','.jsonl','.csv','.svg','.sh','.trace','.smt2','.tex'}


def included():
    for path in sorted(ROOT.rglob('*')):
        if not path.is_file():continue
        relative=path.relative_to(ROOT)
        if relative.parts[0] not in DIRS and relative.as_posix() not in FILES:continue
        if any(p in {'__pycache__','.git','target','.venv'} for p in relative.parts):continue
        if path.suffix in {'.pyc','.log','.tmp'}:continue
        yield path,relative.as_posix()


def check_text(name,data,tokens):
    text=data.decode('utf-8-sig')
    assert not re.search('[\u3400-\u9fff]',text),f'Non-English text: {name}'
    assert not re.search(r'[A-Za-z]:[\\/](?:Users|Space)|/(?:srv|home)/[A-Za-z0-9_-]+',text),f'Host-specific path: {name}'
    for token in tokens:
        assert token.casefold() not in text.casefold(),f'Forbidden identity token in {name}'


def scan(path,name,tokens):
    assert name.isascii(),f'Non-English path: {name}'
    if path.suffix in TEXT or name in FILES:check_text(name,path.read_bytes(),tokens)
    if name.endswith('.tar.gz'):
        with tarfile.open(path) as tar:
            for member in tar:
                assert not member.issym() and not member.islnk()
                assert not member.name.startswith('/') and '..' not in Path(member.name).parts
                assert not member.uname and not member.gname and member.uid==member.gid==0
                if not member.isfile():continue
                data=tar.extractfile(member).read()
                if member.name.endswith('.gz'):data=gzip.decompress(data)
                check_text(name+':'+member.name,data,tokens)


def main(args):
    import check_results
    check_results.main()
    files=list(included())
    for path,name in files:scan(path,name,args.forbidden_token)
    print(f'PASS anonymous content scan: {len(files)} files; nested SMT evidence checked')
    if args.scan_only:return
    output=Path(args.output).resolve()
    if output.exists():raise FileExistsError('Refusing to overwrite an existing distribution: '+str(output))
    output.parent.mkdir(parents=True,exist_ok=True)
    manifest=[]
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for path,name in files:
            data=path.read_bytes();manifest.append(hashlib.sha256(data).hexdigest()+'  '+name)
            info=zipfile.ZipInfo('macroatlas-anonymous/'+name,date_time=(2026,1,1,0,0,0))
            info.create_system=3;info.external_attr=(0o100755 if name=='lib/open-wbo' or name.endswith('.sh') else 0o100644)<<16
            info.compress_type=zipfile.ZIP_DEFLATED;z.writestr(info,data)
        z.writestr('macroatlas-anonymous/SHA256SUMS','\n'.join(manifest)+'\n')
    digest=hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix('.zip.sha256').write_text(digest+'  '+output.name+'\n')
    print(f'Wrote {output.name}: {len(files)} files, {output.stat().st_size:,} bytes, SHA-256 {digest}')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',default='output/macroatlas-anonymous.zip')
    p.add_argument('--scan-only',action='store_true')
    p.add_argument('--forbidden-token',action='append',default=[],help='Additional private identity token to reject; repeatable')
    main(p.parse_args())
