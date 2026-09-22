#!/usr/bin/env python3
"""Rebuild tables, failure lists and publication figures exclusively from validated raw results."""
import argparse
import collections
import csv
import json
import math
import pathlib
import statistics
from common import is_solved, save_json
from validate_results import validate


def quantile(values, q):
    s = sorted(values)
    if not s:
        return None
    i = (len(s)-1)*q;lo = int(i);hi = min(lo+1,len(s)-1)
    return s[lo]+(s[hi]-s[lo])*(i-lo)


def aggregate(rows, timeout):
    groups = collections.defaultdict(list)
    for r in rows:
        groups[(r["task"], r["variant"])].append(r)
    medians = {}
    for key, values in groups.items():
        # A task is common-solved only when all requested repeats solve; missing runs are rejected earlier.
        solved = all(is_solved(v) for v in values)
        medians[key] = dict(values[0], totalSec=statistics.median(float(v["totalSec"]) if is_solved(v) else 2*timeout for v in values),
                            solved=solved, repeats=len(values), peakRssKb=max(float(v["peakRssKb"]) for v in values))
    return medians


def par2(rows, timeout):
    return statistics.mean(float(r["totalSec"]) if is_solved(r) else 2*timeout for r in rows)


def analyze(directory, plots=True):
    rows, manifest = validate(directory)
    out = directory / "processed";out.mkdir(exist_ok=True)
    timeout = manifest["timeoutSec"]
    data = aggregate(rows, timeout)
    variants = sorted({v for _, v in data})
    summaries = []
    for v in variants:
        vals = [r for (t, x), r in data.items() if x == v]
        summaries.append(dict(variant=v, tasks=len(vals), solved=sum(r["solved"] for r in vals),
                              PAR2=par2([r for r in rows if r["variant"]==v],timeout),
                              solvedRuns=sum(is_solved(r) for r in rows if r["variant"]==v),
                              totalWallSec=sum(float(r["totalSec"]) for r in rows if r["variant"]==v),
                              peakRssMiB=max(r["peakRssKb"] for r in vals)/1024,
                              statuses=dict(collections.Counter(r["status"] for r in rows if r["variant"]==v)),
                              macroUsed=sum(r["solverMode"]=="MACRO" for r in vals),
                              fallbackReasons=dict(collections.Counter(r["fallbackReason"] for r in vals if r["fallbackReason"])),
                              fallbackCount=sum(r["status"]=="FALLBACK" or r.get("fallbackUsed","").lower()=="true" for r in vals)))
    baseline, macro = ("atlas-b", "macro") if manifest["suite"]=="matched" else ("original", "auto")
    common = [];outcomes=collections.Counter();failures=[]
    for task in sorted({t for t, _ in data}):
        left=data.get((task,baseline));right=data.get((task,macro))
        if not left or not right:
            continue
        outcomes[("both" if left["solved"] and right["solved"] else "only_baseline" if left["solved"] else "only_macro" if right["solved"] else "neither")]+=1
        if left["solved"] and right["solved"]:
            ratio=left["totalSec"]/right["totalSec"]
            common.append(dict(task=task,baselineSec=left["totalSec"],macroSec=right["totalSec"],speedup=ratio,
                               B=right["B"],K=right["K"],fiberCount=right["fiberCount"],modelBytes=right["modelBytes"],
                               baselineVars=left["vars"],macroVars=right["vars"],baselineModelBytes=left["modelBytes"]))
            if ratio<0.5:
                failures.append(dict(task=task,reason="Macro >2x slower",speedup=ratio))
        elif left["solved"]!=right["solved"]:
            failures.append(dict(task=task,reason="Only baseline solved" if left["solved"] else "Only macro solved"))
    ratios=[r["speedup"] for r in common]
    for summary in summaries:
        field = "baselineSec" if summary["variant"] == baseline else "macroSec"
        summary["medianCommonRuntime"] = statistics.median(r[field] for r in common) if common else None
    stats={"commonSolved":len(common),"outcomes":dict(outcomes),"medianSpeedup":statistics.median(ratios) if ratios else None,
           "geometricMeanSpeedup":math.exp(statistics.mean(map(math.log,ratios))) if ratios else None,
           "p25":quantile(ratios,.25),"p75":quantile(ratios,.75),"pilot":manifest["pilot"],
           "repeats":manifest["repeats"],"timingStatistic":"median of available planned repeats; unsolved repeat gets PAR-2 penalty"}
    save_json(out/"performance.json",summaries);save_json(out/"comparison.json",stats)
    save_json(out/"failure-analysis.json",failures)
    encoding=[]
    for v in variants:
        subset=[r for r in rows if r["variant"]==v]
        record={"variant":v}
        for field in ["B","K","searchNodeUniverse","vars","backendTotalClauses","modelBytes","fiberCount","qStates"]:
            values=[float(r[field]) for r in subset if r[field] not in {"",None}]
            record[field+"Median"]=statistics.median(values) if values else None
            record[field+"Available"]=len(values)
        encoding.append(record)
    save_json(out/"encoding.json",encoding)
    repairs=[r for r in rows if r["objectiveKind"]=="REPAIR"]
    save_json(out/"repair.json",{"runs":len(repairs),"verifiedSat":sum(r["status"]=="SAT" and r["verification"]=="PASSED" for r in repairs),
                                 "objectiveMismatches":0,"note":"validate_results already rejected mismatched common-solved tuples"})
    for name, records in [("table-performance.csv",summaries),("common-solved.csv",common),
                          ("task-summary.csv",list(data.values())),("table-repair.csv",repairs),("table-encoding.csv",encoding)]:
        if records:
            with (out/name).open("w",newline="") as f:
                w=csv.DictWriter(f,fieldnames=list(records[0]),lineterminator="\n");w.writeheader();w.writerows(records)
    (out/"FAILURE_ANALYSIS.md").write_text("# Failure analysis\n\n" + ("PILOT ONLY; no performance claim.\n\n" if manifest["pilot"] else "") +
                                         "\n".join("- %s: %s" % (r["task"],r["reason"]) for r in failures)+"\n")
    if plots:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        def finish(name, xlabel, ylabel):
            if manifest["pilot"]:
                plt.gcf().text(.5, .99, "PILOT ONLY - no performance claim", ha="center", va="top", fontsize=8)
            plt.xlabel(xlabel);plt.ylabel(ylabel);plt.tight_layout();plt.savefig(out/(name+".pdf"));plt.close()
        for v in variants:
            times=sorted(r["totalSec"] for (t,x),r in data.items() if x==v and r["solved"])
            plt.plot(range(1,len(times)+1),times,label=v)
        plt.legend();finish("cactus","Solved tasks","End-to-end seconds")
        if common:
            x=[r["baselineSec"] for r in common];y=[r["macroSec"] for r in common]
            plt.scatter(x,y);plt.xscale("log");plt.yscale("log");lo=min(x+y);hi=max(x+y);plt.plot([lo,hi],[lo,hi],"k--")
            finish("runtime-scatter",baseline+" seconds",macro+" seconds")
            valid=[r for r in common if r["B"] and r["K"]]
            if valid:
                reductions=[float(r["B"])/float(r["K"]) for r in valid]
                plt.hist(reductions);finish("encoding-reduction","B/K","Common-solved tasks")
                plt.scatter(reductions,[r["speedup"] for r in valid]);plt.yscale("log");finish("speedup-vs-kernel","B/K","Speedup")
        components=["analysisSec","registrySec","fiberSec","encodingSec","solverSec","decodeSec","verifySec"]
        bottom=[0.0]*len(variants)
        for field in components:
            heights=[statistics.median([float(r[field] or 0) for r in rows if r["variant"]==v and is_solved(r)] or [0]) for v in variants]
            plt.bar(variants,heights,bottom=bottom,label=field);bottom=[x+y for x,y in zip(bottom,heights)]
        plt.legend(fontsize="small");finish("overhead","Variant","Median component seconds (excludes residual JVM/IO)")
        ablations=[r for r in rows if r["task"].startswith("ablation/")]
        if ablations:
            labels=sorted({r["task"].split('/')[-1].replace('.trace','')+":"+r["variant"] for r in ablations})
            heights=[statistics.median(float(r["totalSec"]) if is_solved(r) else 2*timeout for r in ablations
                                      if r["task"].split('/')[-1].replace('.trace','')+":"+r["variant"]==label) for label in labels]
            plt.bar(labels,heights);plt.xticks(rotation=40,ha="right");finish("ablation","Prespecified correct configuration","Median penalized seconds")
        unary=[r for r in rows if r["task"].startswith("unary/k")]
        if unary:
            for variant in variants:
                ks=sorted({int(pathlib.Path(r["task"]).stem[1:]) for r in unary if r["variant"]==variant})
                ys=[statistics.median(float(r["totalSec"]) if is_solved(r) else 2*timeout for r in unary
                                      if r["variant"]==variant and int(pathlib.Path(r["task"]).stem[1:])==k) for k in ks]
                plt.plot(ks,ys,marker="o",label=variant)
            plt.legend();finish("unary-scaling","Target X-chain length","Median penalized seconds")
        fibers=[r for r in rows if r["solverMode"]=="MACRO" and r["fiberCount"] and r["encodingSec"]]
        if fibers:
            plt.scatter([float(r["fiberCount"]) for r in fibers],[float(r["encodingSec"]) for r in fibers])
            finish("fiber-overhead","Fiber catalog size","Encoding generation seconds")
    return stats


if __name__ == "__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("directory",type=pathlib.Path);p.add_argument("--no-plots",action="store_true")
    a=p.parse_args();print(json.dumps(analyze(a.directory,not a.no_plots),indent=2))
