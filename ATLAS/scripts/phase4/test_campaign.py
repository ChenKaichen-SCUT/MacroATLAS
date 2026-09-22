import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

from campaign import partition, load_plan, merge_phase
from common import FIELDS, save_json, save_csv, sha256
from isolation import allocate, cpu_set, oom_kills


class CampaignTests(unittest.TestCase):
    def test_cpu_groups_never_split_smt_or_oversubscribe(self):
        groups = [(0, 6), (1, 7), (2, 8), (3, 9), (4, 10), (5, 11)]
        workers, reserved = allocate(groups, 2)
        assigned = [cpu_set(x) for x in workers]
        self.assertEqual(len(assigned[0]), len(assigned[1]))
        self.assertFalse(assigned[0] & assigned[1])
        self.assertFalse((assigned[0] | assigned[1]) & cpu_set(reserved))
        self.assertEqual(set(range(12)), assigned[0] | assigned[1] | cpu_set(reserved))
        for group in groups:
            self.assertTrue(any(set(group) <= slot for slot in assigned+[cpu_set(reserved)]))
        with self.assertRaises(ValueError): allocate(groups, 6)

    def test_partition_covers_tasks_once_and_is_deterministic(self):
        records = [dict(task=f'{family}/{i}.trace', family=family) for family in ['a', 'b'] for i in range(17)]
        workers = partition(records, 4, 100)
        self.assertEqual(workers, partition(records, 4, 100))
        self.assertEqual(sorted(r['task'] for r in records), sorted(r['task'] for s in workers for r in s))
        self.assertLessEqual(max(map(len, workers))-min(map(len, workers)), 1)

    def test_cgroup_oom_requires_kernel_evidence(self):
        self.assertEqual(0, oom_kills({'memory.events': 'low 0\nhigh 10\nmax 17\noom 0\noom_kill 0'}))
        self.assertEqual(2, oom_kills({'memory.events': 'oom 3\noom_kill 2'}))

    def test_merge_keeps_every_pair_and_rejects_missing_worker_runs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            env = {k: 'fixed' for k in ['commit', 'applicationSha256', 'java', 'solverSha256', 'alloySha256', 'machine']}
            records = [dict(task='a.trace', family='f', sha256='a'), dict(task='b.trace', family='f', sha256='b')]
            plan = dict(output=str(root), environment=env)
            save_json(root/'plan.json', plan)
            phase = dict(id='matched', suite='matched', tasks=records, repeats=1, root='/inputs', taskListHash='all', workers=[])
            for i, record in enumerate(records):
                directory = root/'matched'/'workers'/str(i)
                directory.mkdir(parents=True)
                worker = dict(config=dict(id=str(i)), output=str(directory))
                phase['workers'].append(worker)
                jobs, rows = [], []
                for variant in ['atlas-b', 'macro']:
                    job = dict(record, variant=variant, repeat=1)
                    folder = directory/variant;folder.mkdir()
                    row = {field: '' for field in FIELDS}
                    row.update({k:v for k,v in job.items() if k in FIELDS})
                    row.update(status='SAT', solverMode='MACRO' if variant=='macro' else 'ATLAS_B', verification='PASSED',
                               B=3, b=1, p=0, objectiveKind='MIN_EXPANDED_SIZE', objectivePrimary=0, objectiveSecondary=2)
                    save_json(folder/'command.json', dict(job, commit='fixed'))
                    save_json(folder/'result.json', row)
                    for name in ['metadata.json','analysis.json','timing.json','verification.json']:save_json(folder/name, {})
                    (folder/'stdout.csv').touch();(folder/'stderr.log').touch()
                    rows.append(row);jobs.append(job)
                save_json(directory/'manifest.json', env)
                save_json(directory/'expected_runs.json', jobs)
                save_csv(directory/'raw.csv', rows)
            merged = merge_phase(plan, phase)
            self.assertEqual(4, len(list(merged.glob('*/command.json'))))
            from validate_results import validate
            self.assertEqual(4, len(validate(merged)[0]))
            missing = dict(phase, id='incomplete', workers=phase['workers'][:1])
            (root/'incomplete').mkdir()
            with self.assertRaisesRegex(ValueError, 'incomplete'): merge_phase(plan, missing)


if __name__ == '__main__': unittest.main()
