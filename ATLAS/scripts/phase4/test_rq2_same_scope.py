import pathlib
import tempfile
import unittest

from rq2_same_scope import do_method, distribution


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


if __name__ == '__main__':
    unittest.main()
