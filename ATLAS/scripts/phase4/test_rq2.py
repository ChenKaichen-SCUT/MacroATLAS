import json
import pathlib
import subprocess
import tempfile
import unittest
from types import SimpleNamespace

from rq2 import ATLAS, JAR, JAVA, JAVAC, dist, do_job, trace_stats


class Rq2Tests(unittest.TestCase):
    def test_trace_metadata_and_quantiles(self):
        text = '0,1;1,1::0\n---\n1,0::0\n---\n!,X,F,G\n'
        stats = trace_stats(text)
        self.assertEqual((2, 1, 1, 1, 2),
            (stats['numAP'], stats['positiveTraces'], stats['negativeTraces'],
             stats['minTraceLength'], stats['maxTraceLength']))
        self.assertEqual(dict(count=3, min=1, p25=2.0, median=3.0, p75=4.0, max=5),
                         dist([1, 3, 5]))

    def test_started_job_is_never_launched_again(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            job = dict(batch='b2', jobId='fake-atlas-b', metricSource='TRANSLATE_ONLY')
            folder = root / 'jobs/b2/fake-atlas-b'
            folder.mkdir(parents=True)
            (folder / 'started.json').write_text('{"attempt": 1}')
            result = do_job(root, {}, job, '2,3')
            self.assertEqual('INTERRUPTED_UNRECORDED', result['status'])
            self.assertEqual(1, result['attempt'])
            self.assertEqual(result, do_job(root, {}, job, '2,3'))
            self.assertEqual([], list(folder.glob('model-*.stdout')))

    def test_cnf_callback_exits_before_sat_solver(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            (root / 'tiny.als').write_text('sig A {}\nrun { some A } for 3\n')
            subprocess.run([str(JAVAC), '-cp', str(JAR), '-d', str(root),
                            str(ATLAS / 'scripts/phase4/Rq2Translate.java')], check=True)
            result = subprocess.run([str(JAVA), '-Xmx512m',
                '-Djava.library.path=' + str(ATLAS / 'lib'),
                '-cp', str(root) + ':' + str(JAR), 'Rq2Translate', str(root / 'tiny.als')],
                text=True, capture_output=True, check=True)
            output = json.loads(result.stdout)
            self.assertEqual('TRANSLATED_ONLY', output['status'])
            self.assertFalse(output['solverInvoked'])
            self.assertGreater(output['vars'], 0)
            self.assertGreater(output['backendTotalClauses'], 0)


if __name__ == '__main__':
    unittest.main()
