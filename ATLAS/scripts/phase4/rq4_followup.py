#!/usr/bin/env python3
"""New RQ4 cases: certified Boolean controls and increasing unary demand."""
import argparse
import csv
import itertools
import json
import pathlib
import random

from common import digest, save_json, sha256
from synthetic import evaluate, parse_formula


SEED = 20260924 + 1000
ALPHABET = '!,X,F,G,&,|,->'


def conjunction(names):
    if len(names)==1:return names[0]
    return '&('+names[0]+','+conjunction(names[1:])+')'


def truth_table(ap=6):
    return [(bits,) for bits in itertools.product((0,1),repeat=ap)]


def pulse_and_random(seed, length=16, count=32):
    if length<3 or count<length:
        raise ValueError('Need all pulse positions and the zero trace')
    items=[tuple((int(i==j),) for i in range(length)) for j in range(length-1)]
    items.append(tuple((0,) for _ in range(length)))
    seen=set(items);rng=random.Random(seed)
    while len(items)<count:
        candidate=tuple((rng.randrange(2),) for _ in range(length-1))+((0,),)
        if candidate not in seen:
            seen.add(candidate);items.append(candidate)
    return items


def trace_text(states):
    return ';'.join(','.join(map(str,state)) for state in states)+'::'+str(len(states)-1)


def write_case(output,name,formula,traces,B,b,ap,axis,value,regime,target_depth,target_binary,
               certified_min_nodes=None,certified_min_binary=None,seed=SEED):
    if B<ap or b<target_binary or len(traces)!=len(set(traces)):
        raise ValueError('Invalid or duplicate RQ4 follow-up traces')
    target=parse_formula(formula)
    positives=[];negatives=[]
    for states in traces:
        (positives if evaluate(target,states,len(states)-1) else negatives).append(trace_text(states))
    if not positives or not negatives:
        raise ValueError('Need positive and negative witnesses')
    path=output/(name+'.trace')
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():raise ValueError('Refusing to overwrite '+str(path))
    path.write_text('\n'.join(positives)+'\n---\n'+'\n'.join(negatives)+'\n---\n'+ALPHABET+
                    '\n---\n['+str(B-ap)+']\n---\n'+formula+'\n')
    record=dict(task=name+'.trace',seed=seed,target=formula,B=B,b=b,AP=ap,
        positive=len(positives),negative=len(negatives),length=len(traces[0]),
        profile='none',protectedRequested=0,requiredPropositions=[],alphabet=ALPHABET,
        axis=axis,axisValue=value,regime=regime,targetUnaryDepth=target_depth,
        targetBinaryNodes=target_binary,traceSetHash=digest([trace_text(x) for x in traces]),
        certifiedMinNodes=certified_min_nodes if certified_min_nodes is not None else '',
        certifiedMinBinary=certified_min_binary if certified_min_binary is not None else '',
        construction='complete_boolean_truth_table' if certified_min_nodes is not None else 'common_pulse_and_random_traces',
        rawTraceSha256=sha256(path))
    save_json(path.with_suffix('.json'),record)
    return record


def generate(output, seed=SEED):
    if output.exists():raise ValueError('Use a new follow-up directory')
    boolean=truth_table(6)
    unary=pulse_and_random(seed)
    records=[]
    # Common examples; each larger B is paired with a genuinely deeper target.
    # Actual learned size is checked after the one-attempt formal campaign.
    for B in (7,9,11):
        depth=B-1
        records.append(write_case(output,'rq4f_unary_B/B%02d'%B,'X('*depth+'x0'+')'*depth,
            unary,B,1,1,'B',B,'small_b_long_unary',depth,0,seed=seed))
    # On all 2^6 one-state valuations, conjunction of the first n variables
    # depends essentially on each of those n variables. Binary fan-in two
    # forces >=n-1 binary nodes; >=n literals then force >=2n-1 total nodes.
    for n in (4,5,6):
        B=2*n-1
        records.append(write_case(output,'rq4f_boolean_B/B%02d'%B,
            conjunction(['x%d'%i for i in range(n)]),boolean,B,n-1,6,
            'B',B,'large_b_short_unary',0,n-1,B,n-1,seed=seed))
    fixed_formula=conjunction(['x%d'%i for i in range(6)])
    # Pure B axis: identical formula, 64 traces, AP and b. The independent
    # certificate makes B<11 bounded UNSAT and B>=11 satisfiable.
    for B in (7,9,12):
        records.append(write_case(output,'rq4f_fixed_B/B%02d'%B,
            fixed_formula,boolean,B,5,6,'B_fixed_target',B,
            'large_b_short_unary',0,5,11,5,seed=seed))
    # Fixed hard Boolean function and traces; vary only the allowed b. Its
    # certified optimum always uses five binary nodes, not the literal shortcut.
    for b in (5,6,7,8):
        records.append(write_case(output,'rq4f_binary_budget/b%02d'%b,
            fixed_formula,boolean,21,b,6,'b',b,'large_b_short_unary',0,5,11,5,seed=seed))
    save_json(output/'manifest.json',dict(seed=seed,cases=len(records),runs=2*len(records),
        tasks=records,suiteHash=digest(records),
        stoppingRule='All new prespecified IDs once per algorithm; no old RQ4 case is rerun',
        certification='Complete 2^6 one-state truth table: n essential propositions require n-1 binary and 2n-1 total nodes in any fan-in-2 formula DAG',
        limitation='Unary B-series deliberately co-scales B with target depth; fixed-target B series is a separate certified bounded SAT/UNSAT transition'))
    print(json.dumps(dict(cases=len(records),runs=2*len(records),output=str(output))))


def audit(campaign):
    """State explicitly which scaling claims the observed one-attempt runs support."""
    with (campaign/'rq4_paper_data.csv').open() as f:
        rows=list(csv.DictReader(f))
    if len(rows)!=26 or len({(r['task'],r['variant']) for r in rows})!=26:
        raise ValueError('Expected exactly 13 new cases x 2 algorithms')
    certified=[];unary=[]
    for row in rows:
        item=dict(task=row['task'],algorithm=row['algorithm'],status=row['status'],
                  B=int(row['B']),b=int(row['b']),targetUnaryDepth=int(row['targetUnaryDepth']),
                  learnedDagNodes=int(row['learnedDagNodes']) if row['learnedDagNodes'] else None,
                  learnedBinaryNodes=int(row['learnedBinaryNodes']) if row['learnedBinaryNodes'] else None,
                  costScope=int(row['costScope']) if row['costScope'] else None)
        if row['construction']=='complete_boolean_truth_table':
            item['certifiedMinNodes']=int(row['certifiedMinNodes'])
            item['certifiedMinBinary']=int(row['certifiedMinBinary'])
            item['certifiedExpectedStatus']='UNSAT' if item['B']<item['certifiedMinNodes'] else 'SAT'
            item['observedOptimumMatchesCertificate']=(
                (item['learnedDagNodes']==item['certifiedMinNodes'] and
                 item['learnedBinaryNodes']==item['certifiedMinBinary'])
                if row['status']=='SAT' else True) if row['status']==item['certifiedExpectedStatus'] else (
                    None if row['status']=='TIMEOUT' else False)
            certified.append(item)
        else:
            item['actualSizeReachesBound']=(item['learnedDagNodes']==item['B']) if row['status']=='SAT' else None
            unary.append(item)
    if len(certified)!=20 or len(unary)!=6:
        raise ValueError('Missing certified control or unary scaling cases')
    result=dict(cases=13,runs=26,certifiedBoolean=certified,unaryDemand=unary,
        controlCertificate='Complete Boolean truth table independently forces n-1 binary and 2n-1 total nodes',
        observedBooleanMatches=all(r['observedOptimumMatchesCertificate'] is True for r in certified),
        observedUnaryBoundReached=all(r['actualSizeReachesBound'] is True for r in unary),
        note='A timeout leaves the corresponding observed property unresolved, never true. B and target depth co-scale in unary series; do not describe this as a fixed-target pure-B experiment.')
    save_json(campaign/'rq4f_design_audit.json',result)
    print(json.dumps(dict(observedBooleanMatches=result['observedBooleanMatches'],
                          observedUnaryBoundReached=result['observedUnaryBoundReached'],
                          output=str(campaign/'rq4f_design_audit.json'))))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command',required=True)
    g=sub.add_parser('generate');g.add_argument('--output',type=pathlib.Path,required=True)
    g.add_argument('--seed',type=int,default=SEED)
    a=sub.add_parser('audit');a.add_argument('--campaign',type=pathlib.Path,required=True)
    args=p.parse_args()
    if args.command=='generate':generate(args.output.resolve(),args.seed)
    else:audit(args.campaign.resolve())


if __name__=='__main__':main()
