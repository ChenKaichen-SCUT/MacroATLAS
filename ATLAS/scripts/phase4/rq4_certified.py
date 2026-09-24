#!/usr/bin/env python3
"""Certified RQ4 unary/binary families and a semantics-neutral q stress axis."""

import argparse
import collections
import csv
import itertools
import json
from pathlib import Path

from common import FIELDS, digest, save_csv, save_json, sha256
from rq4 import rows_so_far
from rq4_followup import conjunction, trace_text
from synthetic import evaluate, parse_formula


SEED = 20260924 + 3000
UNARY_DEPTHS = (4, 6, 8, 10, 12, 14, 16, 20, 24, 28, 32, 40)
BINARY_ARITIES = (2, 3, 4, 5, 6, 7)
PROFILE_STATES = (1, 2, 4, 8, 16)


def paired_unary(depth, prefix_bits=4):
    """Each unlike-labelled pair agrees everywhere except at position depth."""
    assert depth >= prefix_bits
    positive, negative = [], []
    for bits in itertools.product((0, 1), repeat=prefix_bits):
        prefix = tuple((bit,) for bit in bits) + ((0,),) * (depth - prefix_bits)
        positive.append(prefix + ((1,), (0,)))
        negative.append(prefix + ((0,), (0,)))
    return positive, negative


def write_case(root, name, formula, positive, negative, alphabet, B, b, ap,
               axis, axis_value, construction, optimum, binary_nodes, marker=None):
    path = root / (name + '.trace')
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or B < ap or len(positive) == 0 or len(negative) == 0:
        raise ValueError('Invalid or already-generated RQ4 certified case: ' + name)
    target = parse_formula(formula)
    if any(not evaluate(target, states, len(states)-1) for states in positive):
        raise ValueError('Positive witness mislabelled: ' + name)
    if any(evaluate(target, states, len(states)-1) for states in negative):
        raise ValueError('Negative witness mislabelled: ' + name)
    encoded_positive = [trace_text(states) for states in positive]
    encoded_negative = [trace_text(states) for states in negative]
    if len(set(encoded_positive + encoded_negative)) != len(encoded_positive + encoded_negative):
        raise ValueError('Duplicate RQ4 certified trace: ' + name)
    text = ('\n'.join(encoded_positive) + '\n---\n' + '\n'.join(encoded_negative) +
            '\n---\n' + alphabet + '\n---\n[' + str(B-ap) + ']\n---\n' + formula + '\n')
    if marker is not None:
        text += '---\n// RQ4_NEUTRAL_PROFILE_STATES=' + str(marker) + '\n'
    path.write_text(text)
    record = dict(task=name + '.trace', seed=SEED, target=formula, B=B, b=b,
                  AP=ap, positive=len(positive), negative=len(negative),
                  length=len(positive[0]), profile='none', protectedRequested=0,
                  requiredPropositions=[], alphabet=alphabet, axis=axis,
                  axisValue=axis_value, regime=construction,
                  targetUnaryDepth=optimum-1 if construction in ('certified_unary','neutral_profile') else 0,
                  targetBinaryNodes=binary_nodes, certifiedMinNodes=optimum,
                  certifiedMinBinary=binary_nodes, construction=construction,
                  rawTraceSha256=sha256(path),
                  traceSetHash=digest(encoded_positive + encoded_negative))
    if marker is not None:
        record['auxiliaryProfileStates'] = marker
        record['certificate'] = 'All auxiliary states accept; only profile state count changes'
    elif construction == 'certified_unary':
        record['certificate'] = ('X-only grammar: every formula is X^i(x0). Each opposite-label '
                                 'pair agrees before depth d and after depth d; only i=d separates it.')
    else:
        record['certificate'] = ('Complete 2^n one-state truth table: each variable is essential; '
                                 'n leaves and n-1 binary nodes are necessary and sufficient.')
    save_json(path.with_suffix('.json'), record)
    return record


def generate(output):
    if output.exists():
        raise ValueError('Use a fresh RQ4 certified input directory')
    ab, profile = output/'ab', output/'profile'
    ab_records, profile_records = [], []
    for depth in UNARY_DEPTHS:
        positive, negative = paired_unary(depth)
        formula = 'X(' * depth + 'x0' + ')' * depth
        ab_records.append(write_case(ab, 'rq4c_unary/d%02d' % depth, formula,
            positive, negative, 'X', depth+1, 0, 1, 'certified_unary_depth', depth,
            'certified_unary', depth+1, 0))
    for n in BINARY_ARITIES:
        positive, negative = [], []
        for bits in itertools.product((0, 1), repeat=n):
            (positive if all(bits) else negative).append((bits,))
        ab_records.append(write_case(ab, 'rq4c_binary/n%02d' % n,
            conjunction(['x%d' % i for i in range(n)]), positive, negative,
            '&', 2*n-1, n-1, n, 'certified_binary_arity', n,
            'certified_binary', 2*n-1, n-1))
    # One fixed semantic task, fixed traces and B. The comment is ignored by
    # Alloy/ATLAS-B; only Macro's experiment-only profile preserves m states.
    positive, negative = paired_unary(2, prefix_bits=2)
    for m in PROFILE_STATES:
        profile_records.append(write_case(profile, 'rq4c_profile/q%02d' % m,
            'X(X(x0))', positive, negative, 'X', 17, 0, 1,
            'neutral_profile_states', m, 'neutral_profile', 3, 0, marker=m))
    save_json(output/'manifest.json', dict(seed=SEED, ab=ab_records, profile=profile_records,
        abCases=len(ab_records), profileCases=len(profile_records),
        expectedRuns=2*len(ab_records)+len(profile_records),
        strictOnce=True, stoppingRule='All fixed cases once; no outcome-based replacement',
        qBaseline='Only Macro runs on q=1,2,4,8,16; ATLAS-B does not observe the auxiliary comment',
        designLimitation='The q auxiliary states are intentionally not language-minimized.'))
    print(json.dumps(dict(abCases=len(ab_records), profileCases=len(profile_records),
                          expectedRuns=2*len(ab_records)+len(profile_records), output=str(output))))


def campaign_status(path, label):
    if not (path/'plan.json').exists():
        return dict(label=label, completed=0, expected=0, state='PENDING', statuses={})
    plan = json.loads((path/'plan.json').read_text())
    expected = sum(len(phase['tasks'])*len(phase['variants'])*phase['repeats'] for phase in plan['phases'])
    _, rows = rows_so_far(path)
    keys = [(row['task'], row['variant'], row['repeat']) for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError('Duplicate recorded RQ4 certified attempt in '+str(path))
    state = json.loads((path/'state.json').read_text())['status']
    return dict(label=label, completed=len(rows), expected=expected, state=state,
                statuses=dict(collections.Counter(row['status'] for row in rows)),
                byVariant={variant:dict(collections.Counter(row['status'] for row in rows if row['variant']==variant))
                           for variant in sorted({v for phase in plan['phases'] for v in phase['variants']})})


def status(ab_campaign, profile_campaign):
    ab = campaign_status(ab_campaign, 'A+B')
    profile = campaign_status(profile_campaign, 'C')
    print('RQ4 certified A+B %d/%d | C %d/%d | total %d/%d' % (
        ab['completed'], ab['expected'], profile['completed'], profile['expected'],
        ab['completed']+profile['completed'], ab['expected']+profile['expected']))
    print(json.dumps(dict(ab=ab, profile=profile), ensure_ascii=False))


def audit_ab(campaign):
    with (campaign/'rq4_paper_data.csv').open(newline='') as source:
        rows = list(csv.DictReader(source))
    if len(rows) != 2*(len(UNARY_DEPTHS)+len(BINARY_ARITIES)):
        raise ValueError('Missing A/B RQ4 certified runs')
    audit = []
    for row in rows:
        optimum = int(row['certifiedMinNodes'])
        binary = int(row['certifiedMinBinary'])
        if row['status'] == 'SAT':
            valid = (row['verification']=='PASSED' and
                     int(row['learnedDagNodes']) == optimum and
                     int(row['learnedBinaryNodes']) == binary)
        elif row['status'] in ('TIMEOUT', 'ERROR'):
            valid = None
        else:
            valid = False
        audit.append(dict(task=row['task'], algorithm=row['algorithm'], status=row['status'],
                          certifiedOptimum=optimum, certifiedBinary=binary,
                          learnedSize=row['learnedDagNodes'] or None,
                          learnedBinary=row['learnedBinaryNodes'] or None,
                          observedCertificate=valid))
    if any(row['observedCertificate'] is False for row in audit):
        raise ValueError('Solved result conflicts with an independent RQ4 certificate')
    save_json(campaign/'rq4c_ab_audit.json',dict(rows=audit,
        completed=sum(row['observedCertificate'] is True for row in audit),
        unresolved=sum(row['observedCertificate'] is None for row in audit),
        note='Timeout/error is unresolved, never counted as certificate agreement.'))
    print(json.dumps(dict(validated=sum(row['observedCertificate'] is True for row in audit),
                          unresolved=sum(row['observedCertificate'] is None for row in audit))))


def report_profile(campaign):
    plan = json.loads((campaign/'plan.json').read_text())
    phase, raw = rows_so_far(campaign)
    tasks = {row['task']: row for row in json.loads(
        (Path(phase['root']).parent/'rq4-inspected-manifest.json').read_text())['tasks']}
    if json.loads((campaign/'state.json').read_text())['status'] != 'COMPLETE':
        raise ValueError('Profile campaign has not completed')
    if len(raw) != len(PROFILE_STATES) or {(row['task'],row['variant']) for row in raw} != \
            {(name,'macro') for name in tasks}:
        raise ValueError('Missing/duplicate profile runs')
    rows=[]
    for source in sorted(raw,key=lambda item:item['task']):
        task=tasks[source['task']]
        requested=int(task['auxiliaryProfileStates'])
        if task['q'] != requested or task['recognizedFeatures'] != f'RQ4NeutralProfile({requested})':
            raise ValueError('Profile state inspection differs from requested m')
        row=dict(source,algorithm='MacroATLAS',axis='neutral_profile_states',axisValue=requested,
                 requestedQ=requested,actualQ=task['q'],traceSetHash=task['traceSetHash'],
                 runCommit=plan['environment']['commit'],timeoutSec=plan['timeoutSec'],
                 solved=source['status'] in ('SAT','UNSAT') and
                        (source['status']=='UNSAT' or source['verification']=='PASSED'))
        if row['qStates'] and int(row['qStates']) != requested:
            raise ValueError('Runtime q differs from inspected q')
        rows.append(row)
    fields=list(rows[0])
    save_csv(campaign/'rq4c_profile_data.csv',rows,fields)
    save_json(campaign/'rq4c_profile_summary.json',dict(cases=len(rows),runs=len(rows),
        statuses=dict(collections.Counter(row['status'] for row in rows)),
        inputSha256=sha256(campaign/'inputs.tar.gz'),
        paperCsvSha256=sha256(campaign/'rq4c_profile_data.csv'),
        design='Fixed traces, target, X-only alphabet, B=17, b=0; only a non-minimized all-accepting auxiliary profile changes',
        qRows=[{key:row.get(key,'') for key in ('task','status','requestedQ','actualQ','totalSec',
                 'fiberCount','vars','backendTotalClauses','encodingSec','solverSec','learnedDagNodes')}
               for row in rows]))
    print(json.dumps(dict(cases=len(rows),statuses=dict(collections.Counter(row['status'] for row in rows)))))


def summarize(ab_campaign, profile_campaign, output):
    with (ab_campaign/'rq4_paper_data.csv').open(newline='') as source:
        ab=list(csv.DictReader(source))
    with (profile_campaign/'rq4c_profile_data.csv').open(newline='') as source:
        profile=list(csv.DictReader(source))
    rows=[dict(runGroup='A+B',**row) for row in ab]+[dict(runGroup='C',**row) for row in profile]
    keys=[(row['task'],row['variant'],row['repeat']) for row in rows]
    if len(rows)!=2*(len(UNARY_DEPTHS)+len(BINARY_ARITIES))+len(PROFILE_STATES) or len(set(keys))!=len(keys):
        raise ValueError('Incomplete/duplicate final RQ4 certified table')
    fields=['runGroup']
    for row in rows:
        for field in row:
            if field not in fields:fields.append(field)
    output.mkdir(parents=True,exist_ok=True)
    save_csv(output/'rq4c_paper_data.csv',rows,fields)
    save_json(output/'rq4c_summary.json',dict(cases=len(UNARY_DEPTHS)+len(BINARY_ARITIES)+len(PROFILE_STATES),
        runs=len(rows),statusByGroupAndVariant={group+'_'+variant:dict(collections.Counter(
            row['status'] for row in rows if row['runGroup']==group and row['variant']==variant))
            for group,variant in (('A+B','atlas-b'),('A+B','macro'),('C','macro'))},
        abCsvSha256=sha256(ab_campaign/'rq4_paper_data.csv'),
        profileCsvSha256=sha256(profile_campaign/'rq4c_profile_data.csv'),
        paperCsvSha256=sha256(output/'rq4c_paper_data.csv'),
        note='A/B are paired; C is Macro-only because ATLAS-B ignores the auxiliary profile. Every run is one attempt.'))
    print(json.dumps(dict(cases=len(UNARY_DEPTHS)+len(BINARY_ARITIES)+len(PROFILE_STATES),runs=len(rows),
                          paperFile=str(output/'rq4c_paper_data.csv'))))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    g=sub.add_parser('generate');g.add_argument('--output',type=Path,required=True)
    s=sub.add_parser('status');s.add_argument('--ab-campaign',type=Path,required=True);s.add_argument('--profile-campaign',type=Path,required=True)
    a=sub.add_parser('audit-ab');a.add_argument('--campaign',type=Path,required=True)
    p=sub.add_parser('report-profile');p.add_argument('--campaign',type=Path,required=True)
    final=sub.add_parser('summarize');final.add_argument('--ab-campaign',type=Path,required=True)
    final.add_argument('--profile-campaign',type=Path,required=True);final.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.command=='generate':generate(args.output)
    elif args.command=='status':status(args.ab_campaign,args.profile_campaign)
    elif args.command=='audit-ab':audit_ab(args.campaign)
    elif args.command=='report-profile':report_profile(args.campaign)
    else:summarize(args.ab_campaign,args.profile_campaign,args.output)


if __name__=='__main__':main()
