import json
import pathlib
import tempfile
import unittest

from rq1 import MODES, case_input, prepare, run_job, sha256
from types import SimpleNamespace


class Rq1Tests(unittest.TestCase):
    def test_generated_cases_are_deterministic_and_cover_all_rq1_profiles(self):
        first = [case_input(i, 20260923) for i in range(8)]
        self.assertEqual(first, [case_input(i, 20260923) for i in range(8)])
        self.assertEqual(8, len({item[1]["family"] for item in first}))
        self.assertEqual(3, len(MODES))
        self.assertEqual("literal", case_input(8, 20260923)[1]["inputPattern"])
        self.assertEqual("literal", case_input(12, 20260923)[1]["inputPattern"])
        for contents, info in first:
            self.assertIn("---", contents)
            self.assertNotIn("U,", contents)
            self.assertGreaterEqual(info["B"], info["numAP"])

    def test_prepared_inputs_are_unique_and_have_no_solver_attempts(self):
        with tempfile.TemporaryDirectory() as temp:
            output = pathlib.Path(temp) / "unique"
            prepare(SimpleNamespace(output=output, count=100, offset=1000, seed=20260923))
            manifest = json.loads((output / "dataset.json").read_text())
            hashes = [case["inputSha256"] for case in manifest["cases"]]
            self.assertEqual(100, len(set(hashes)))
            self.assertEqual(100, len(list((output / "inputs").rglob("*.trace"))))
            self.assertFalse((output / "jobs").exists())

    def test_interrupted_attempt_is_recorded_without_second_solver_launch(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            contents, case = case_input(100000, 20260923)
            case["task"] = "plain/tiny_100000.trace"
            source = root / "inputs" / case["task"]
            source.parent.mkdir(parents=True)
            source.write_text(contents)
            case["inputSha256"] = sha256(source)
            folder = root / "jobs" / case["id"] / "oracle"
            folder.mkdir(parents=True)
            (folder / "started.json").write_text(json.dumps({"attempt": 1}))
            result = run_job(root, {"sourceCommit": "test"}, case, "oracle", "2,3", "")
            self.assertEqual("INTERRUPTED_UNRECORDED", result["status"])
            self.assertFalse((folder / "stdout.log").exists())
            self.assertEqual(result, run_job(root, {"sourceCommit": "test"}, case, "oracle", "2,3", ""))


if __name__ == "__main__":
    unittest.main()
