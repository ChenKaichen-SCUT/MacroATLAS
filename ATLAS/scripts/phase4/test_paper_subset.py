import collections
import json
import unittest

from common import ATLAS
from paper_subset import select


class PaperSubsetTests(unittest.TestCase):
    def setUp(self):
        self.population = json.loads((ATLAS/'docs/phase4/preflight/paper-provenance.json').read_text())

    def test_quarter_contains_all_five_categories_without_duplicates(self):
        selected = select(self.population, .25, 20260922)
        self.assertEqual(156, len(selected))
        self.assertEqual(156, len({r['task'] for r in selected}))
        self.assertEqual({'baselines/baseline_alloy_all.csv': 121,
                          'peterson/peterson_alloy.csv': 8, 'robot/robot_alloy.csv': 5,
                          'voting/voting_alloy.csv': 2, 'weakening/weakening_alloy_gr1_new.csv': 20},
                         dict(collections.Counter(r['table'] for r in selected)))
        self.assertTrue({r['task'] for r in selected} <= {r['task'] for r in self.population})

    def test_selection_is_independent_of_input_order_and_observed_outcomes(self):
        expected = select(self.population, .25, 20260922)
        self.assertEqual(expected, select(list(reversed(self.population)), .25, 20260922))
        # Only provenance is passed to the selector; no baseline results are read.
        self.assertNotEqual(expected, select(self.population, .25, 20260923))
        half = select(self.population, .5, 20260922)
        self.assertEqual(312, len(half))
        self.assertTrue({r['task'] for r in expected} <= {r['task'] for r in half})

    def test_full_selection_and_invalid_requests(self):
        self.assertEqual(623, len(select(self.population, 1, 20260922)))
        for fraction in [0, -1, 1.1, .001, float('nan')]:
            with self.assertRaises(ValueError): select(self.population, fraction, 1)
        with self.assertRaises(ValueError): select(self.population + self.population[:1], .25, 1)


if __name__ == '__main__': unittest.main()
