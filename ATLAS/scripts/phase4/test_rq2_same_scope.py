import pathlib
import tempfile
import unittest

from rq2_same_scope import do_method, distribution, remaining


class SameScopeTests(unittest.TestCase):
    def test_started_attempt_is_never_relaunched(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            job = {'jobId': 'case-1'}
            folder = root / 'jobs/case-1/atlas-b'
            folder.mkdir(parents=True)
            (folder / 'started.json').write_text('{"attempt":1}\n')
            result = do_method(root, {}, job, 'atlas-b', '0')
            self.assertEqual('INTERRUPTED_UNRECORDED', result['status'])
            self.assertEqual(1, result['attempt'])
            self.assertEqual(result, do_method(root, {}, job, 'atlas-b', '0'))
            self.assertFalse((folder / 'emit.stdout').exists())

    def test_distribution_drops_no_statuses_implicitly(self):
        self.assertEqual({'n': 2, 'median': 1.5, 'min': 1, 'max': 2}, distribution([1, 2]))
        self.assertEqual(0, distribution([])['n'])

    def test_remaining_covers_small_bounds_without_repeating_completed_cases(self):
        rows = [{'batch': 'b2', 'task': 'plain/%04d.trace' % index,
                 'inputSha256': str(index), 'family': 'baseTest', 'qStates': '1',
                 'b': '2', 'B': '3' if index < 84 else '15'}
                for index in range(623)]
        frozen = {'sourceSha256': 'source-hash', 'attemptsPerMethodCaseScope': 1,
                  'jobs': rows[84:284]}
        picks = remaining(rows, frozen, 'source-hash')
        self.assertEqual(423, len(picks))
        self.assertEqual(623, len({(row['batch'], row['task']) for row, _, _ in picks} |
                              {(job['batch'], job['task']) for job in frozen['jobs']}))
        self.assertEqual(84, sum(row['B'] == '3' and scope == 3 for row, _, scope in picks))
        self.assertTrue(all(scope <= int(row['B']) for row, _, scope in picks))


if __name__ == '__main__':
    unittest.main()
