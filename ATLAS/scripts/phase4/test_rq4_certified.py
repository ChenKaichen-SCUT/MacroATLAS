"""Independent construction checks for the certified RQ4 input families."""

import json
import tempfile
import unittest
from pathlib import Path

from rq4_certified import (BINARY_ARITIES, PROFILE_STATES, UNARY_DEPTHS,
                           generate, paired_unary)


class CertifiedRq4InputsTest(unittest.TestCase):
    def test_unary_pairs_force_the_exact_x_depth(self):
        for depth in UNARY_DEPTHS:
            positive, negative = paired_unary(depth)
            self.assertEqual((16, 16), (len(positive), len(negative)))
            for pos, neg in zip(positive, negative):
                self.assertEqual(pos[:depth], neg[:depth])
                self.assertNotEqual(pos[depth], neg[depth])
                self.assertEqual(pos[depth+1:], neg[depth+1:])
                for earlier in range(depth):
                    self.assertEqual(pos[earlier], neg[earlier])

    def test_manifest_has_fresh_ids_and_full_boolean_truth_tables(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)/'inputs'
            generate(root)
            manifest = json.loads((root/'manifest.json').read_text())
            self.assertEqual(2*(len(UNARY_DEPTHS)+len(BINARY_ARITIES))+len(PROFILE_STATES),
                             manifest['expectedRuns'])
            names = [row['task'] for row in manifest['ab']+manifest['profile']]
            self.assertEqual(len(names), len(set(names)))
            self.assertTrue(all(name.startswith('rq4c_') for name in names))
            for n in BINARY_ARITIES:
                record = next(row for row in manifest['ab'] if row['task'].endswith('/n%02d.trace'%n))
                self.assertEqual((1,2**n-1,2*n-1,n-1),
                                 (record['positive'],record['negative'],record['certifiedMinNodes'],
                                  record['certifiedMinBinary']))
                self.assertEqual('&', record['alphabet'])
            originals=[]
            for m in PROFILE_STATES:
                record = next(row for row in manifest['profile'] if row['auxiliaryProfileStates']==m)
                text=(root/'profile'/record['task']).read_text()
                self.assertEqual('X', record['alphabet'])
                self.assertTrue(text.endswith('// RQ4_NEUTRAL_PROFILE_STATES=%d\n'%m))
                originals.append(text.rsplit('---',1)[0])
            self.assertEqual(1,len(set(originals)))


if __name__=='__main__':unittest.main()
