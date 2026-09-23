import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

from campaign import partition, load_plan, merge_phase, phase_variants, progress, worker_command, restrict_tasks
from common import FIELDS, save_json, save_csv, sha256
from isolation import allocate, cpu_set, oom_kills


class CampaignTests(unittest.TestCase):
    def test_explicit_followup_restricts_tasks_and_rejects_missing_names(self):
        self.assertEqual(['b', 'c'], restrict_tasks(['a', 'b', 'c'], {'c', 'b'}))
        with self.assertRaisesRegex(ValueError, 'absent'):
            restrict_tasks(['a', 'b'], {'c'})

    def test_phase_variants_support_selective_and_legacy_plans(self):
        self.assertEqual(['auto'], phase_variants(dict(suite='auto', variants=['auto'])))
        self.assertEqual(['original', 'auto'], phase_variants(dict(suite='auto')))

    def test_selective_phase_controls_worker_command_and_expected_count(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            worker = dict(
                config=dict(id='w00', cpus='2,3', memoryMb=4096, unit='test-worker'),
                configFile=str(root/'worker.json'), tasks=str(root/'supported_tasks.txt'),
                output=str(root/'output'), log=str(root/'worker.log'),
                records=[dict(task='a.trace'), dict(task='b.trace')])
            phase = dict(id='e5-auto', suite='auto', variants=['auto'], root='/inputs',
                         repeats=1, perTaskBudgets=False, workers=[worker])
            plan = dict(python='/venv/python', timeoutSec=180, b=2, seed=1, heap='4g', java='/jdk/java',
                        gate='/gate.json', pilot=False, controllerUnit='controller', phases=[phase])
            command = worker_command(plan, phase, worker)
            index = command.index('--variants')
            self.assertEqual(['--variants', 'auto'], command[index:index+2])
            self.assertEqual(2, progress(plan)[0]['expected'])

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
