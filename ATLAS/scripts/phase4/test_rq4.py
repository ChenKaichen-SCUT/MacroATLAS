"""RQ4 preregistration and complete paper-table checks without solver runs."""
import csv
import json
import pathlib
import tempfile
import unittest

from common import FIELDS, save_csv, save_json
from rq4 import generate, report


class Rq4Tests(unittest.TestCase):
    def test_grid_and_paper_table_cover_each_pair_once(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=pathlib.Path(temporary)
            raw_inputs=base/'inputs'
            generate(raw_inputs)
            manifest=json.loads((raw_inputs/'manifest.json').read_text())
            self.assertEqual((manifest['cases'],manifest['runs']),(30,60))
            self.assertEqual({r['axis'] for r in manifest['tasks']},
                             {'B','unary_depth','b','required_count','shape'})
            self.assertEqual(len({r['task'] for r in manifest['tasks']}),30)
            ready=base/'ready'
            for task in manifest['tasks']:
                task.update(p=0,K=min(task['B'],3*task['b']+2),q=1,
                            compressionPotential=0,recognizedFeatures='')
            save_json(ready/'rq4-inspected-manifest.json',manifest)
            campaign=base/'campaign'
            worker=campaign/'e8-synthetic/workers/w00'
            worker.mkdir(parents=True)
            root=ready/'matched_u_free'
            save_json(campaign/'plan.json',{'phases':[{'id':'e8-synthetic','root':str(root),
                'workers':[{'output':str(worker)}]}]})
            save_json(campaign/'state.json',{'status':'COMPLETE'})
            save_json(campaign/'e8-synthetic/complete.json',{'status':'COMPLETE'})
            rows=[]
            for task in manifest['tasks']:
                for variant,seconds in [('atlas-b',10),('macro',5)]:
                    row={k:'' for k in FIELDS}
                    row.update(task=task['task'],variant=variant,status='SAT',verification='PASSED',
                               totalSec=seconds,objectivePrimary=0,objectiveSecondary=3)
                    rows.append(row)
            save_csv(worker/'raw.csv',rows)
            (campaign/'e8-synthetic/merged').mkdir(parents=True)
            save_csv(campaign/'e8-synthetic/merged/raw.csv',rows)
            report(campaign)
            with (campaign/'rq4_paper_data.csv').open() as f:
                paper=list(csv.DictReader(f))
            with (campaign/'rq4_pairs.csv').open() as f:
                pairs=list(csv.DictReader(f))
            self.assertEqual((len(paper),len(pairs)),(60,30))
            self.assertEqual({p['speedup'] for p in pairs},{'2.0'})
            self.assertEqual(json.loads((campaign/'rq4_summary.json').read_text())['bothSolved'],30)


if __name__=='__main__':unittest.main()
