#!/usr/bin/env python3
"""Test independent SMT semantics against frozen reference outcomes and profiles."""

import csv
import dataclasses
from pathlib import Path
import sys
import unittest

import z3

sys.path.insert(0,str(Path(__file__).resolve().parent))
from rq1_exact_smt import ExactEncoding, Task, evaluate_witness, parse_task


ATLAS = Path(__file__).resolve().parents[2]
ROOT = ATLAS / 'datasets/benchmark'


def read_rows(path):
    with path.open(newline='') as handle:
        return list(csv.DictReader(handle))


class ExactSmtIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if z3.get_version_string() != '4.14.1':
            raise RuntimeError('Install the artifact requirement: Z3 4.14.1.')

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

    def test_weakening_smt_rejects_temporal_strict_descendant_in_frozen_text(self):
        path=ATLAS/'datasets/benchmark/weakening/weaken_antecedent/weaken_antecedent_10_10_10.trace'
        task=dataclasses.replace(parse_task(path,10,2,'weakening_b2'),positive=(),negative=())
        nodes=[{'id':0,'label':'x0'}, {'id':1,'label':'x1'},
               {'id':2,'label':'G','left':1},
               {'id':3,'label':'&','left':0,'right':2},
               {'id':4,'label':'->','left':3,'right':1},
               {'id':5,'label':'G','left':4}]
        encoding=ExactEncoding(task,len(nodes))
        for node in nodes:
            i=node['id'];encoding.solver.add(encoding.kind_is(i,node['label']))
            if 'left' in node:encoding.solver.add(encoding.left[i]==node['left'])
            if 'right' in node:encoding.solver.add(encoding.right[i]==node['right'])
        self.assertEqual(encoding.solver.check(),z3.unsat)
        self.assertFalse(evaluate_witness(task,{'nodes':nodes,'root':5,'size':6,'binaryNodes':2}))

    def test_all_623_inputs_are_frozen_and_parsed(self):
        rows=read_rows(ATLAS/'datasets/benchmark/manifest.csv')
        self.assertEqual(len(rows),623)
        for row in rows:
            task=parse_task(ROOT/row['task'],int(row['B']),int(row['b']),row['category'])
            self.assertEqual(task.source_sha256,row['input_sha256'])

    def test_125_plain_cases_match_frozen_reference(self):
        reference = {r['task']: r for r in read_rows(ATLAS/'results/raw/rq1_small_smt.csv')}
        observed = 0
        for path in sorted((ATLAS/'datasets/small/plain').glob('*.trace')):
            row = reference['plain/' + path.name]
            task = parse_task(path, int(row['B']), int(row['b']), 'tiny_plain')
            actual_status, actual_size = 'UNSAT', None
            for size in range(1, task.B + 1):
                encoding = ExactEncoding(task, size)
                encoding.solver.set(timeout=5000)
                result = encoding.solver.check()
                self.assertNotEqual(result, z3.unknown, path.stem)
                if result == z3.sat:
                    self.assertTrue(evaluate_witness(task, encoding.witness(encoding.solver.model())))
                    actual_status, actual_size = 'SAT', size
                    break
            self.assertEqual(actual_status, row['oracleStatus'], path.stem)
            if actual_status == 'SAT':
                self.assertEqual(actual_size, int(row['oracleSecondary']), path.stem)
            observed += 1
        self.assertEqual(observed, 125)

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
        rows={row['task']:row for row in read_rows(ATLAS/'datasets/benchmark/manifest.csv')}
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
