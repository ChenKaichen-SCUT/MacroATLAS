#!/usr/bin/env python3
"""Deterministic favorable/control tasks, independently labelled on infinite lassos."""
import argparse
import itertools
import json
import pathlib
import random
from common import digest, save_json


def parse_formula(text):
    at=0
    def parse():
        nonlocal at
        start=at
        while at<len(text) and text[at] not in "(,)":
            at+=1
        name=text[start:at].strip()
        if at==len(text) or text[at]!="(":
            if not name.startswith("x") or not name[1:].isdigit():
                raise ValueError("Literal must be x<number>")
            return (name,)
        at+=1;children=[parse()]
        if at<len(text) and text[at]==",":
            at+=1;children.append(parse())
        if at>=len(text) or text[at]!=")":
            raise ValueError("Unbalanced formula")
        at+=1
        if name not in {"!","X","F","G","&","|","->"} or len(children)!=(2 if name in {"&","|","->"} else 1):
            raise ValueError("Outside supported U-free grammar")
        return (name,*children)
    formula=parse()
    if at!=len(text):
        raise ValueError("Trailing formula input")
    return formula


def render(node):
    return node[0] if len(node)==1 else node[0]+"("+",".join(map(render,node[1:]))+")"


def evaluate(formula, states, loop):
    """Direct future traversal, not MacroATLAS's normalizer/quotient or solver encoding."""
    n=len(states)
    def nxt(i):return i+1 if i+1<n else loop
    future=[]
    for start in range(n):
        seen=set();order=[];i=start
        while i not in seen:
            seen.add(i);order.append(i);i=nxt(i)
        future.append(order)
    def visit(node):
        op=node[0]
        if len(node)==1:
            return [bool(s[int(op[1:])]) for s in states]
        left=visit(node[1])
        if op=="!":return [not x for x in left]
        if op=="X":return [left[nxt(i)] for i in range(n)]
        if op=="F":return [any(left[j] for j in future[i]) for i in range(n)]
        if op=="G":return [all(left[j] for j in future[i]) for i in range(n)]
        right=visit(node[2])
        if op=="&":return [a and b for a,b in zip(left,right)]
        if op=="|":return [a or b for a,b in zip(left,right)]
        return [not a or b for a,b in zip(left,right)]
    return visit(formula)[0]


def write_task(directory, name, formula, seed, B, b, ap, traces, length, profile="none", protected=0, alphabet=None,
               positive_count=None, negative_count=None):
    if min(traces,length,ap,B)<1 or b<0 or B<ap:
        raise ValueError("Invalid synthetic parameters")
    node=parse_formula(formula)
    positive_goal=traces if positive_count is None else positive_count
    negative_goal=traces if negative_count is None else negative_count
    if min(positive_goal,negative_goal)<1:raise ValueError("Both class counts must be positive")
    def check_ap(n):
        if len(n)==1 and int(n[0][1:])>=ap:raise ValueError("Target AP out of range")
        for c in n[1:]:check_ap(c)
    check_ap(node)
    randomizer=random.Random(seed);positive=[];negative=[];seen=set()
    # Balanced labels if both classes exist; never relabel a trace to force a balance.
    for _ in range(max(1000,max(positive_goal,negative_goal)*1000)):
        states=[[randomizer.randrange(2) for _ in range(ap)] for _ in range(length)]
        loop=randomizer.randrange(length)
        text=";".join(",".join(map(str,s)) for s in states)+"::"+str(loop)
        if text in seen:continue
        seen.add(text)
        label=evaluate(node,states,loop)
        target=positive if label else negative
        if len(target)<(positive_goal if label else negative_goal):target.append(text)
        if len(positive)==positive_goal and len(negative)==negative_goal:break
    if not positive or not negative:
        raise ValueError("Cannot generate both classes; target may be a tautology/contradiction or length too short")
    # `traces` means per class, not total. Insufficient unique traces is explicitly recorded.
    constraints=[]
    if profile=="nnf":constraints.append("fact { all n: Neg | n.l in Literal }")
    elif profile=="required":constraints.append("fact { x0 in childrenAndSelfOf[root] }")
    elif profile!="none":raise ValueError("Unknown safe profile")
    if protected:
        # Protect a literal plus the first k-1 X nodes of an X-chain; exact root/direct-edge constraints.
        word=[];current=node
        while len(current)==2 and current[0]=="X":word.append("X");current=current[1]
        if len(current)!=1 or protected>len(word)+1:
            raise ValueError("Protected scaling requires an X-chain and p<=chain length+1")
        if protected==1:
            constraints.append("fact { %s in childrenAndSelfOf[root] }"%current[0])
            # A RequiredProp alone does not protect identity. p=1 uses named root unary instead.
            if not word:raise ValueError("p=1 requires at least one X")
            constraints.extend(["one sig X0 extends X {}","fact { root = X0 }"])
        else:
            for i in range(protected-1):constraints.append("one sig X%d extends X {}"%i)
            constraints.append("fact { root = X0 }")
            for i in range(protected-2):constraints.append("fact { X%d.l = X%d }"%(i,i+1))
            constraints.extend(["fact { %s in childrenAndSelfOf[root] }"%current[0],"fact { %s in childrenOf[X%d] }"%(current[0],protected-2)])
    operators=alphabet or "!,X,F,G,&,|,->"
    text="\n".join(positive)+"\n---\n"+"\n".join(negative)+"\n---\n"+operators+"\n---\n[%d]\n---\n%s\n"%(max(0,B-ap),formula)
    if constraints:text+="---\n"+"\n".join(constraints)+"\n"
    path=directory/(name+".trace");path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():raise ValueError("Refusing to overwrite generated task")
    path.write_text(text)
    record=dict(task=name+".trace",seed=seed,target=formula,B=B,b=b,AP=ap,positive=len(positive),negative=len(negative),
                requestedPositive=positive_goal,requestedNegative=negative_goal,length=length,profile=profile,protectedRequested=protected,alphabet=operators)
    save_json(path.with_suffix(".json"),record)
    return record


def suite(output, seed):
    records=[]
    # One factor at a time: retain a common base rather than an unmanageable full Cartesian product.
    configs=[]
    for k in [1,2,4,6,8,10,14,20,30]:
        configs.append(("unary/k%02d"%k,"X("*k+"x0"+")"*k,k+1,0,1,4,max(4,k+1),"none",0))
    def boolean_tree(leaves):
        if len(leaves)==1:return leaves[0]
        middle=len(leaves)//2;return "&("+boolean_tree(leaves[:middle])+","+boolean_tree(leaves[middle:])+")"
    for ap in [2,3,4]:configs.append(("control/ap%d"%ap,boolean_tree(["x%d"%i for i in range(ap)]),2*ap-1,ap-1,ap,8,8,"none",0))
    for B in [5,7,9,11,15,21,31]:configs.append(("B/%d"%B,"X(X(x0))",B,1,1,8,8,"none",0))
    for b in [0,1,2,3,4]:configs.append(("b/%d"%b,"X(X(x0))",9,b,1,8,8,"none",0))
    for p in [0,1,2,4,8]:configs.append(("p/%d"%p,"X("*8+"x0"+")"*8,11,0,1,8,12,"none",p))
    for ap in [1,2,4,8]:configs.append(("AP/%d"%ap,"X(X(x0))",11,1,ap,8,8,"none",0))
    for count in [4,8,16,32,64]:configs.append(("traces/%d"%count,"X(X(x0))",9,1,1,count,8,"none",0))
    for length in [4,8,16,32]:configs.append(("length/%d"%length,"X(X(x0))",9,1,1,8,length,"none",0))
    for profile in ["none","nnf","required"]:configs.append(("ablation/"+profile,"X(X(x0))",7,1,1,8,8,profile,0))
    for i,c in enumerate(configs):
        name,formula,B,b,ap,count,length,profile,p=c
        # Matched trace seeds are identical within profile ablation; raw constraints differ explicitly.
        case_seed=seed if name.startswith("ablation/") else seed+i
        records.append(write_task(output,name,formula,case_seed,B,b,ap,count,length,profile,p,
                                  alphabet="!,&,|,->" if name.startswith("control/") else None))
    for direction in ["positive","negative"]:
        for count in [4,8,16,32,64]:
            records.append(write_task(output,direction+"/%d"%count,"X(X(x0))",seed+100+count,9,1,1,8,8,
                                      positive_count=count if direction=="positive" else 8,
                                      negative_count=count if direction=="negative" else 8))
    save_json(output/"manifest.json",{"seed":seed,"tasks":records,"suiteHash":digest(records),"stoppingRule":"No adaptive pruning by observed winner; run every prespecified task"})
    return records


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--output",type=pathlib.Path,required=True);p.add_argument("--seed",type=int,default=20260924)
    p.add_argument("--target");p.add_argument("--B",type=int,default=9);p.add_argument("--b",type=int,default=1);p.add_argument("--ap",type=int,default=1)
    p.add_argument("--traces",type=int,default=8);p.add_argument("--length",type=int,default=8)
    p.add_argument("--positive",type=int);p.add_argument("--negative",type=int)
    a=p.parse_args()
    if a.output.exists():p.error("Use a new output directory")
    if a.target:write_task(a.output,"custom",a.target,a.seed,a.B,a.b,a.ap,a.traces,a.length,positive_count=a.positive,negative_count=a.negative)
    else:suite(a.output,a.seed)
