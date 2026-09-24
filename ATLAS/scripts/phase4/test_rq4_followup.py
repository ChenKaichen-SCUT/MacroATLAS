"""Independent checks that new RQ4 controls cannot collapse to literals."""
import itertools
import json
import pathlib
import tempfile
import unittest

from rq4_followup import generate


class Rq4FollowupTests(unittest.TestCase):
    def test_boolean_controls_have_complete_truth_tables_and_essential_variables(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=pathlib.Path(temporary)/'rq4f'
            generate(root)
            manifest=json.loads((root/'manifest.json').read_text())
            self.assertEqual((manifest['cases'],manifest['runs']),(13,26))
            self.assertTrue(all(r['task'].startswith('rq4f_') for r in manifest['tasks']))
            truth_tables=[r for r in manifest['tasks'] if r['construction']=='complete_boolean_truth_table']
            self.assertEqual(len(truth_tables),10)
            self.assertEqual(len({r['traceSetHash'] for r in truth_tables}),1)
            for record in truth_tables:
                text=(root/record['task']).read_text()
                sections=text.split('---')
                positive=sections[0].strip().splitlines()
                negative=sections[1].strip().splitlines()
                self.assertEqual(len(positive)+len(negative),64)
                n=record['certifiedMinBinary']+1
                self.assertEqual(record['certifiedMinNodes'],2*n-1)
                if record['axis']=='B_fixed_target':
                    self.assertEqual(record['certifiedMinNodes'],11)
                    self.assertEqual(record['b'],5)
                seen={}
                for label,items in [(True,positive),(False,negative)]:
                    for item in items:
                        states,loop=item.split('::')
                        self.assertEqual(loop,'0')
                        bits=tuple(int(x) for x in states.split(','))
                        self.assertEqual(len(bits),6)
                        self.assertNotIn(bits,seen)
                        seen[bits]=label
                        self.assertEqual(label,all(bits[:n]))
                self.assertEqual(set(seen),set(itertools.product((0,1),repeat=6)))
                for i in range(n):
                    witness=[1]*6
                    self.assertTrue(seen[tuple(witness)])
                    witness[i]=0
                    self.assertFalse(seen[tuple(witness)])

    def test_unary_series_uses_one_common_trace_set_and_growing_witness(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=pathlib.Path(temporary)/'rq4f'
            generate(root)
            tasks=json.loads((root/'manifest.json').read_text())['tasks']
            unary=[r for r in tasks if r['regime']=='small_b_long_unary']
            self.assertEqual([r['B'] for r in unary],[7,9,11])
            self.assertEqual([r['targetUnaryDepth'] for r in unary],[6,8,10])
            self.assertEqual(len({r['traceSetHash'] for r in unary}),1)
            self.assertEqual([r['b'] for r in unary],[1,1,1])
            self.assertTrue(all(r['positive']+r['negative']==32 for r in unary))


if __name__=='__main__':unittest.main()
