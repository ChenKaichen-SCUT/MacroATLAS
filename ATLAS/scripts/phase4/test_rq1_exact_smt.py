#!/usr/bin/env python3
"""Cross-check the independent SMT semantics against the exhaustive tiny oracle."""

import csv
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

import z3

sys.path.insert(0,str(Path(__file__).resolve().parent))
from rq1_exact_smt import ExactEncoding, Task, evaluate_witness, parse_task


ATLAS = Path(__file__).resolve().parents[2]
ART = ATLAS / 'experiment_artifacts'
ROOT = ATLAS / 'generated/phase4-preflight/matched_u_free'


def read_rows(path):
    with path.open(newline='') as handle:
        return list(csv.DictReader(handle))


class ExactSmtIntegration(unittest.TestCase):
    def test_concrete_verifier_ignores_commented_constraints(self):
        nnf=Task((),(),('!','G'),1,4,0,'nnf_template',
                 'fact { root in G\n // all n: Neg | n.l in Literal\n}', '')
        nested={'nodes':[{'id':0,'label':'x0'},
                         {'id':1,'label':'!','left':0},
                         {'id':2,'label':'!','left':1},
                         {'id':3,'label':'G','left':2}]}
        self.assertTrue(evaluate_witness(nnf,nested))
        required=Task((),(),('G',),2,2,0,'required',
                      'fact { root in G\n x0 in root.*(l+r)\n // x1 in root.*(l+r)\n}', '')
        minimal={'nodes':[{'id':0,'label':'x0'},{'id':1,'label':'G','left':0}]}
        self.assertTrue(evaluate_witness(required,minimal))

    def test_weakening_checks_transitive_children_of_implication(self):
        task=Task((),(),('G','&','->'),2,6,2,'weakening_b2','', '')
        nested_temporal={'nodes':[
            {'id':0,'label':'x0'}, {'id':1,'label':'x1'},
            {'id':2,'label':'G','left':1},
            {'id':3,'label':'&','left':0,'right':2},
            {'id':4,'label':'->','left':3,'right':1},
            {'id':5,'label':'G','left':4}]}
        self.assertFalse(evaluate_witness(task,nested_temporal))

    def test_all_623_inputs_are_frozen_and_parsed(self):
        rows=read_rows(ART/'2026-09-25/rq2-full-623/summary/rq2_full_623_paper_data.csv')
        self.assertEqual(len(rows),623)
        for row in rows:
            task=parse_task(ROOT/row['task'],int(row['B']),int(row['b']),row['category'])
            self.assertEqual(task.source_sha256,row['inputSha256'])

    def test_125_plain_cases_match_independent_exhaustive_oracle(self):
        oracle={row['caseId']:row for row in read_rows(ART/'2026-09-23/rq1-tiny/per-run.csv')
            if row['method']=='oracle' and row['family']=='plain'}
        archive=ART/'2026-09-23/archives/rq1-tiny-primary-1000.tar.gz'
        observed=0
        with tempfile.TemporaryDirectory() as temp,tarfile.open(archive) as tar:
            for member in tar:
                if '/inputs/plain/' not in member.name or not member.name.endswith('.trace'):
                    continue
                path=Path(temp)/Path(member.name).name
                path.write_bytes(tar.extractfile(member).read())
                reference=oracle[path.stem]
                task=parse_task(path,int(reference['B']),int(reference['b']),'plain')
                actual_status,actual_size='UNSAT',0
                for size in range(1,task.B+1):
                    encoding=ExactEncoding(task,size)
                    encoding.solver.set(timeout=5000)
                    result=encoding.solver.check()
                    self.assertNotEqual(result,z3.unknown,path.stem)
                    if result==z3.sat:
                        witness=encoding.witness(encoding.solver.model())
                        self.assertTrue(evaluate_witness(task,witness))
                        actual_status,actual_size='SAT',size
                        break
                self.assertEqual(actual_status,reference['status'],path.stem)
                self.assertEqual(actual_size,int(reference['objectiveSecondary'] or 0),path.stem)
                observed+=1
        self.assertEqual(observed,125)

    def test_one_certified_case_per_official_profile(self):
        examples=[
            ('5to10Traces/0000.trace',3,0),
            ('voting_machine/voting10.trace',4,0),
            ('peterson/base/liveness1.trace',5,0),
            ('robot/RRtrace/order2.trace',9,4),
            ('robot/RAtrace/final21.trace',9,5),
            ('weakening/weaken_antecedent/weaken_antecedent_10_10_10.trace',6,0),
            ('weakening/weaken_consequent/weaken_consequent_10_10_10.trace',7,0),
        ]
        rows={row['task']:row for row in read_rows(ART/'2026-09-25/rq2-full-623/summary/rq2_full_623_paper_data.csv')}
        for name,optimum,kept in examples:
            row=rows[name]
            task=parse_task(ROOT/name,int(row['B']),int(row['b']),row['category'])
            for size in range(1,optimum+1):
                encoding=ExactEncoding(task,size,kept)
                encoding.solver.set(timeout=10000)
                result=encoding.solver.check()
                self.assertEqual(result,z3.sat if size==optimum else z3.unsat,(name,size))
                if result==z3.sat:
                    witness=encoding.witness(encoding.solver.model())
                    self.assertTrue(evaluate_witness(task,witness))
                    self.assertEqual(witness.get('keptEdges',0),kept)


if __name__=='__main__':unittest.main()
