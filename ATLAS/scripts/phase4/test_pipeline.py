import csv
import json
import pathlib
import tempfile
import unittest
import sys
from common import FIELDS, is_solved
from prepare import atlas_format
from run import check_pair, row_from_metadata, execute, choose_variants
from synthetic import parse_formula, render, evaluate, write_task
from analyze import aggregate, par2
from validate_results import validate


class PipelineTests(unittest.TestCase):
    def test_selective_variants_are_ordered_and_suite_safe(self):
        self.assertEqual(['atlas-b', 'macro'], choose_variants('matched'))
        self.assertEqual(['auto'], choose_variants('auto', ['auto']))
        for values in [[], ['original'], ['auto', 'auto']]:
            with self.assertRaises(ValueError):
                choose_variants('matched', values)

    def test_timeout_reaps_the_whole_process_group(self):
        with tempfile.TemporaryDirectory() as temp:
            directory=pathlib.Path(temp)
            code,wall,peak,reason=execute([sys.executable,"-c","import subprocess,time;subprocess.Popen(['sleep','10']);time.sleep(10)"],directory,0.2,0)
            self.assertNotEqual(0,code);self.assertEqual("TIMEOUT",reason)
            self.assertLess(wall,3);self.assertGreater(peak,0)
    def test_formula_labels_on_infinite_lassos(self):
        states=[[0],[1],[0]]
        self.assertTrue(evaluate(parse_formula("F(x0)"),states,0))
        self.assertFalse(evaluate(parse_formula("G(x0)"),states,0))
        self.assertTrue(evaluate(parse_formula("G(F(x0))"),states,0))
        self.assertFalse(evaluate(parse_formula("G(F(x0))"),states,2))
        self.assertTrue(evaluate(parse_formula("X(x0)"),states,2))
        self.assertFalse(evaluate(parse_formula("X(X(X(x0)))"),states,2))
        for text in ["x0","!(x0)","G(->(x0,F(x1)))"]:
            self.assertEqual(text,render(parse_formula(text)))
        for text in ["U(x0,x1)","X(x0,x1)","F(x0)junk"]:
            with self.assertRaises(ValueError):parse_formula(text)

    def test_generation_is_deterministic_and_never_edits_labels(self):
        with tempfile.TemporaryDirectory() as temp:
            root=pathlib.Path(temp)
            for name in ["a","b"]:
                write_task(root/name,"sample","X(x0)",5,5,1,1,4,4)
            self.assertEqual((root/"a/sample.trace").read_bytes(),(root/"b/sample.trace").read_bytes())
            parts=(root/"a/sample.trace").read_text().split("---")
            for expected,part in [(True,parts[0]),(False,parts[1])]:
                for line in part.strip().splitlines():
                    trace,loop=line.split("::");states=[[int(v) for v in s.split(',')] for s in trace.split(';')]
                    self.assertEqual(expected,evaluate(parse_formula("X(x0)"),states,int(loop)))
            self.assertTrue(atlas_format((root/"a/sample.trace").read_text()))
            self.assertFalse(atlas_format("1::0\n---\n0::0\n---\nG(?)"))

    def test_par2_keeps_failures_and_uses_repeat_medians(self):
        rows=[dict(task="t",variant="macro",status=s,outcome="",verification="PASSED",totalSec=t,peakRssKb=100)
              for s,t in [("SAT",1),("SAT",3),("TIMEOUT",180)]]
        result=aggregate(rows,180)[("t","macro")]
        self.assertEqual(3,result["totalSec"])
        self.assertFalse(result["solved"])
        self.assertAlmostEqual((1+3+360)/3,par2(rows,180))
        fallback=dict(rows[0],status="FALLBACK",outcome="SAT",verification="TRACE_PASSED")
        self.assertTrue(is_solved(fallback))

    def test_objective_and_unsat_mismatch_stop_comparison(self):
        left=dict(task="t",repeat=1,variant="atlas-b",status="SAT",objectivePrimary=2,objectiveSecondary=5)
        check_pair([left,dict(left,variant="macro")])
        for bad in [dict(left,variant="macro",objectivePrimary=1),dict(left,variant="macro",objectiveSecondary=4),dict(left,variant="macro",status="UNSAT")]:
            with self.assertRaises(RuntimeError):check_pair([left,bad])

    def test_result_schema_preserves_verification_and_resource_fields(self):
        row=row_from_metadata(dict(status="SAT",solverMode="MACRO",nodeBudget=5,binaryBudget=1,expandedNodeCount=3),
                              dict(status="PASSED"),dict(task="t",family="f",variant="macro",repeat=1),2.1,1024)
        self.assertEqual(set(FIELDS),set(row));self.assertEqual(5,row["B"]);self.assertEqual(3,row["expandedSize"])
        self.assertEqual("PASSED",row["verification"])

    def test_validator_rejects_missing_runs_missing_artifacts_and_changed_results(self):
        with tempfile.TemporaryDirectory() as temp:
            directory=pathlib.Path(temp);folder=directory/"case";folder.mkdir()
            job=dict(task="t",family="f",variant="macro",repeat=1,sha256="input-digest")
            row=row_from_metadata(dict(status="SAT",solverMode="MACRO",nodeBudget=3,binaryBudget=0),
                                  dict(status="PASSED"),job,1.0,1024)
            def save(name,value): (directory/name).write_text(json.dumps(value))
            def csv_row(value):
                with (directory/"raw.csv").open("w",newline="") as f:
                    w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerow(value)
            save("manifest.json",dict(commit="tested"));save("expected_runs.json",[job])
            save("case/command.json",dict(job,commit="tested"));save("case/result.json",row)
            for name in ["metadata.json","analysis.json","timing.json","verification.json"]:save("case/"+name,{})
            (folder/"stdout.csv").touch();(folder/"stderr.log").touch();csv_row(row)
            self.assertEqual(1,len(validate(directory)[0]))
            csv_row(dict(row,totalSec=0.01))
            with self.assertRaisesRegex(AssertionError,"CSV disagrees"):validate(directory)
            csv_row(row);(folder/"verification.json").unlink()
            with self.assertRaisesRegex(AssertionError,"Missing verification"):validate(directory)
            save("case/verification.json",{});save("expected_runs.json",[job,dict(job,repeat=2)])
            with self.assertRaisesRegex(AssertionError,"Missing expected"):validate(directory)


if __name__=="__main__":unittest.main()
