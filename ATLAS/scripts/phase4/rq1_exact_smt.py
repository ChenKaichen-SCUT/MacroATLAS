#!/usr/bin/env python3
"""Independent finite-DAG SMT oracle for the matched U-free benchmark.

The encoding is written directly in Z3, without Alloy, ATLAS-B's model, or
MacroATLAS's automata. Each UNSAT query is saved as replayable SMT-LIB.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

import z3


UNARY = ("!", "X", "F", "G")
BINARY = ("&", "|", "->")
CUSTOM_HASHES = {
    'nnf_template': {'26a1c5cdf634c218b7ec6578b1e99d466faacef0ee46f3f0bf3df29e92cfa4f7',
                     '45efdf2ac6601915ba5a4a2cb7ae27bb967933be1a1beebd11b26b0af231a3cb'},
    'required': {'2d9df7af7d8884e7e857e5f9673e811205ce8a9106b28ecf32780e8687dbbe5b',
                 'd58a9f51f5c1bc20f0078de05342722a1bf972de07a8d4d11d550cf51af247a6',
                 '21281860c5f6cc0bde50084cda9d9817440664e679750da612484f6b1f982da5'},
    'repair': {'3733f60a5df184a1a381e400584e26e4a312f1424d294befcb81814046432891',
               '1a473c559fe6857a0353880925b32cc2275b8a1e9d70b904606e811afb5a9a19'},
    'weakening_b2': {'6793473afd9b8a8ec3a6c146d3e2f3b76d3d7cedbb5603fd69c5a251adad7319'},
    'weakening_b3': {'a20f604f9fd520d01e90555be5a5f8af73e8a77bc912cc2e9a0be57b84057f87'},
}


@dataclass(frozen=True)
class Trace:
    states: tuple[tuple[bool, ...], ...]
    loop: int

    def next(self, pos: int) -> int:
        return pos + 1 if pos + 1 < len(self.states) else self.loop

    def future(self, pos: int) -> tuple[int, ...]:
        seen = []
        while pos not in seen:
            seen.append(pos)
            pos = self.next(pos)
        return tuple(seen)


@dataclass(frozen=True)
class Task:
    positive: tuple[Trace, ...]
    negative: tuple[Trace, ...]
    operators: tuple[str, ...]
    ap: int
    B: int
    b: int
    category: str
    custom: str
    source_sha256: str

    @property
    def traces(self) -> tuple[Trace, ...]:
        return self.positive + self.negative


def parse_task(path: Path, B: int, b: int, category: str) -> Task:
    raw = path.read_bytes()
    parts = raw.decode().split("---")
    if len(parts) < 4:
        raise ValueError("Malformed .trace: fewer than four sections")

    def traces(section: str) -> tuple[Trace, ...]:
        result = []
        for line in section.strip().splitlines():
            if not line.strip():
                continue
            state_part, _, loop_part = line.strip().partition("::")
            states = tuple(tuple(bit.strip() == "1" for bit in state.split(","))
                           for state in state_part.split(";"))
            loop = int(loop_part.split("[")[0]) if loop_part.split("[")[0] else 0
            if not states or not 0 <= loop < len(states):
                raise ValueError("Invalid lasso")
            result.append(Trace(states, loop))
        return tuple(result)

    positive, negative = traces(parts[0]), traces(parts[1])
    all_traces = positive + negative
    if not all_traces:
        raise ValueError("No examples")
    ap = len(all_traces[0].states[0])
    # TaskParser fixes the alphabet from the first example. Both missing and
    # extra columns occur in official voting inputs: absent APs test false,
    # while extra APs cannot be referenced by a formula.
    pad = lambda state: (state[:ap] + (False,) * max(0, ap - len(state)))
    positive = tuple(Trace(tuple(pad(state) for state in trace.states), trace.loop) for trace in positive)
    negative = tuple(Trace(tuple(pad(state) for state in trace.states), trace.loop) for trace in negative)
    allowed_raw = tuple(x.strip() for x in parts[2].strip().split(","))
    if len(allowed_raw) != len(set(allowed_raw)) or not set(allowed_raw) <= set(UNARY + BINARY + ('prop',)):
        raise ValueError("Unsupported alphabet")
    allowed = tuple(x for x in allowed_raw if x != 'prop')
    raw_bound = parts[3].strip()
    parsed_B = (int(raw_bound[1:-1]) if raw_bound.startswith("[")
                else (2 ** int(raw_bound) - 1)) + ap
    if parsed_B != B:
        raise ValueError(f"Recorded B={B} differs from parsed B={parsed_B}")
    custom = parts[5].strip() if len(parts) > 5 else ""
    if category == 'plain':
        if custom:
            raise ValueError('Plain case unexpectedly has a custom constraint')
    elif hashlib.sha256(custom.encode()).hexdigest() not in CUSTOM_HASHES.get(category, set()):
        raise ValueError('Custom constraint does not match the frozen matched benchmark profile')
    return Task(positive, negative, allowed, ap, B, b, category, custom,
                hashlib.sha256(raw).hexdigest())


def _or(items):
    return z3.Or(*items) if items else z3.BoolVal(False)


def _and(items):
    return z3.And(*items) if items else z3.BoolVal(True)


class ExactEncoding:
    def __init__(self, task: Task, size: int, kept_at_least: int = 0):
        self.task, self.size, self.kept_at_least = task, size, kept_at_least
        self.labels = [f"x{i}" for i in range(task.ap)] + [x for x in UNARY + BINARY if x in task.operators]
        self.kind = [z3.Int(f"kind_{i}") for i in range(size)]
        self.left = [z3.Int(f"left_{i}") for i in range(size)]
        self.right = [z3.Int(f"right_{i}") for i in range(size)]
        self.solver = z3.Solver()
        self.values: list[list[list[z3.BoolRef]]] = []
        self._base()
        self._semantics()
        self._custom()

    def kind_is(self, i: int, label: str):
        return self.kind[i] == self.labels.index(label) if label in self.labels else z3.BoolVal(False)

    def is_unary(self, i: int):
        return _or(self.kind_is(i, x) for x in UNARY)

    def is_binary(self, i: int):
        return _or(self.kind_is(i, x) for x in BINARY)

    def choose(self, refs, i: int, exprs):
        return _or(z3.And(refs[i] == j, exprs[j]) for j in range(i))

    def child_kind(self, i: int, port: str, label: str):
        refs = self.left if port == "left" else self.right
        return self.choose(refs, i, [self.kind_is(j, label) for j in range(i)])

    def _base(self):
        t, n, s = self.task, self.size, self.solver
        for i in range(n):
            s.add(self.kind[i] >= 0, self.kind[i] < len(self.labels))
            if i == 0:
                s.add(self.kind[i] < t.ap)
            else:
                s.add(self.left[i] >= 0, self.left[i] < i)
                s.add(self.right[i] >= 0, self.right[i] < i)
            if i < n - 1:
                s.add(_or(z3.Or(z3.And(self.is_unary(j), self.left[j] == i),
                                z3.And(self.is_binary(j),
                                       z3.Or(self.left[j] == i, self.right[j] == i)))
                          for j in range(i + 1, n)))
        for a in range(t.ap):
            s.add(z3.AtMost(*[self.kind_is(i, f"x{a}") for i in range(n)], 1))
        s.add(z3.PbLe([(self.is_binary(i), 1) for i in range(n)], t.b))

    def _semantics(self):
        s, n, task = self.solver, self.size, self.task
        for ti, trace in enumerate(task.traces):
            rows = [[z3.Bool(f"v_{ti}_{i}_{p}") for p in range(len(trace.states))] for i in range(n)]
            self.values.append(rows)
            # On a lasso, every position in the loop sees the entire loop.
            # Prefix positions see their suffix followed by that loop. Build
            # shared linear-size recurrences rather than quadratic OR/AND ASTs.
            future_any, future_all = [], []
            for j in range(n):
                loop_any = _or(rows[j][p] for p in range(trace.loop, len(trace.states)))
                loop_all = _and(rows[j][p] for p in range(trace.loop, len(trace.states)))
                any_row = [loop_any] * len(trace.states)
                all_row = [loop_all] * len(trace.states)
                for p in range(trace.loop - 1, -1, -1):
                    any_row[p] = z3.Or(rows[j][p], any_row[p+1])
                    all_row[p] = z3.And(rows[j][p], all_row[p+1])
                future_any.append(any_row)
                future_all.append(all_row)
            for i in range(n):
                for p in range(len(trace.states)):
                    v = rows[i][p]
                    for a in range(task.ap):
                        s.add(z3.Implies(self.kind_is(i, f"x{a}"), v == trace.states[p][a]))
                    if i == 0:
                        continue
                    lv = self.choose(self.left, i, [rows[j][p] for j in range(i)])
                    rv = self.choose(self.right, i, [rows[j][p] for j in range(i)])
                    for op in task.operators:
                        if op == '!': expr = z3.Not(lv)
                        elif op == 'X': expr = self.choose(self.left, i, [rows[j][trace.next(p)] for j in range(i)])
                        elif op == 'F': expr = self.choose(self.left, i, [future_any[j][p] for j in range(i)])
                        elif op == 'G': expr = self.choose(self.left, i, [future_all[j][p] for j in range(i)])
                        elif op == '&': expr = z3.And(lv, rv)
                        elif op == '|': expr = z3.Or(lv, rv)
                        else: expr = z3.Implies(lv, rv)
                        s.add(z3.Implies(self.kind_is(i, op), v == expr))
            s.add(rows[n-1][0] == (ti < len(task.positive)))

    def _contains(self):
        n, t, s = self.size, self.task, self.solver
        contained = [[z3.Bool(f"has_{i}_{a}") for a in range(t.ap)] for i in range(n)]
        for i in range(n):
            for a in range(t.ap):
                expr = self.kind_is(i, f"x{a}")
                if i:
                    left = self.choose(self.left, i, [contained[j][a] for j in range(i)])
                    right = self.choose(self.right, i, [contained[j][a] for j in range(i)])
                    expr = z3.Or(expr, z3.And(self.is_unary(i), left),
                                 z3.And(self.is_binary(i), z3.Or(left, right)))
                s.add(contained[i][a] == expr)
        return contained

    def _descendants(self):
        n,s=self.size,self.solver
        desc=[[z3.Bool(f'desc_{i}_{j}') for j in range(i+1)] for i in range(n)]
        for i in range(n):
            s.add(desc[i][i])
            for j in range(i):
                left=self.choose(self.left,i,[desc[k][j] if k>=j else z3.BoolVal(False) for k in range(i)])
                right=self.choose(self.right,i,[desc[k][j] if k>=j else z3.BoolVal(False) for k in range(i)])
                s.add(desc[i][j]==z3.Or(z3.And(self.is_unary(i),left),
                                         z3.And(self.is_binary(i),z3.Or(left,right))))
        return desc

    def _custom(self):
        t, n, s = self.task, self.size, self.solver
        text = re.sub(r"/\*[\s\S]*?\*/|//[^\n]*|--[^\n]*", " ", t.custom)
        if t.category == "plain":
            if text.strip():
                raise ValueError("Unexpected custom constraint in plain case")
            return
        if t.category == "nnf_template":
            if "root in G" not in text:
                raise ValueError("Unknown voting constraint")
            s.add(self.kind_is(n-1, "G"))
            if "n.l in Literal" in text:
                for i in range(1,n):
                    s.add(z3.Implies(self.kind_is(i, "!"),
                                     self.choose(self.left, i, [self.kind[j] < t.ap for j in range(i)])))
            return
        if t.category == "required":
            if "root in G" not in text or "no" not in text or "Literal" not in text:
                raise ValueError("Unknown Peterson constraint")
            s.add(self.kind_is(n-1, "G"))
            required = sorted({int(x) for x in re.findall(r"x(\d+)\s+in\s+root\.\*\(l\+r\)", text)})
            for a in required:
                s.add(_or(self.kind_is(i, f"x{a}") for i in range(n)))
            if "root.l in Imply" in text:
                s.add(self.child_kind(n-1, "left", "->"))
                s.add(_or(z3.And(self.left[n-1] == j, self.kind_is(j, "->"),
                                 self.child_kind(j, "right", "F")) for j in range(1,n-1)))
            contained = self._contains()
            for i in range(1,n):
                for a in range(t.ap):
                    left = self.choose(self.left, i, [contained[j][a] for j in range(i)])
                    right = self.choose(self.right, i, [contained[j][a] for j in range(i)])
                    s.add(z3.Implies(self.is_binary(i), z3.Not(z3.And(left,right))))
            return
        if t.category == "repair":
            self._repair_constraints(text)
            return
        if t.category.startswith("weakening_"):
            self._weakening_constraints(text)
            return
        raise ValueError("Unknown matched category: " + t.category)

    def _repair_constraints(self, text: str):
        n, s = self.size, self.solver
        ra = "G0" in text
        names = ({"And0":"&","F0":"F","G0":"G","Neg0":"!","x0":"x0","x2":"x2"} if ra else
                 {"And0":"&","F0":"F","F1":"F","x0":"x0","x1":"x1"})
        edges = ([('And0','G0'),('G0','Neg0'),('Neg0','x2'),('And0','F0'),('F0','x0')] if ra else
                 [('And0','F0'),('F0','x0'),('And0','F1'),('F1','x1')])
        if "maxsome[2]" not in text or "no l & r" not in text or "lone n.~(l+r)" not in text:
            raise ValueError("Unknown repair constraint")
        named = {name:z3.Int(f"named_{name}") for name in names}
        for name, idx in named.items():
            s.add(idx >= 0, idx < n)
            s.add(_or(z3.And(idx == i, self.kind_is(i, names[name])) for i in range(n)))
        s.add(z3.Distinct(*named.values()))
        s.add(self.kind_is(n-1, "&"))
        for i in range(1,n):
            s.add(z3.Implies(self.is_binary(i), self.left[i] != self.right[i]))
            if not ra:
                s.add(z3.Implies(self.kind_is(i,"!"),
                                 self.choose(self.left,i,[self.kind[j] < self.task.ap for j in range(i)])))
        for i in range(n-1):
            incoming = [z3.And(self.is_unary(j),self.left[j]==i) for j in range(i+1,n)]
            incoming += [z3.And(self.is_binary(j),self.left[j]==i) for j in range(i+1,n)]
            incoming += [z3.And(self.is_binary(j),self.right[j]==i) for j in range(i+1,n)]
            s.add(z3.Implies(self.kind[i] >= self.task.ap,z3.AtMost(*incoming,1)))
        kept=[]
        for source,target in edges:
            kept.append(_or(z3.And(named[source]==i,named[target]==j,
                                   z3.Or(z3.And(self.is_unary(i),self.left[i]==j),
                                         z3.And(self.is_binary(i),z3.Or(self.left[i]==j,self.right[i]==j))))
                            for i in range(1,n) for j in range(i)))
        s.add(z3.PbGe([(edge,1) for edge in kept],self.kept_at_least))
        self.repair_names, self.repair_edges = named, edges

    def _weakening_constraints(self, text: str):
        t,n,s=self.task,self.size,self.solver
        consequent=t.category=='weakening_b3'
        if consequent != ('one sig And0' in text) or 'root = G0' not in text or 'l = Imply0' not in text:
            raise ValueError('Unknown weakening template')
        s.add(self.kind_is(n-1,'G'))
        s.add(self.child_kind(n-1,'left','->'))
        desc=self._descendants()
        literal=lambda i: self.kind[i]<t.ap
        child_literal=lambda i,port: self.choose(self.left if port=='left' else self.right,i,
                                                  [literal(j) for j in range(i)])
        child_ap=lambda i,port,a: self.child_kind(i,port,f'x{a}')
        for i in range(1,n):
            if i==n-1:continue
            # The quantified restrictions apply to every Imply node.
            permitted=lambda port: z3.Or(child_literal(i,port),
                *[self.child_kind(i,port,op) for op in ('&','|','!')])
            s.add(z3.Implies(self.kind_is(i,'->'),z3.And(permitted('left'),permitted('right'))))
            for port in ('left','right'):
                for neg in range(1,i):
                    s.add(z3.Implies(z3.And(self.kind_is(i,'->'),
                        (self.left[i] if port=='left' else self.right[i])==neg,
                        self.kind_is(neg,'!')),child_literal(neg,'left')))
            for sub in range(i):
                left_sub=self.choose(self.left,i,
                    [desc[k][sub] if k>=sub else z3.BoolVal(False) for k in range(i)])
                right_sub=self.choose(self.right,i,
                    [desc[k][sub] if k>=sub else z3.BoolVal(False) for k in range(i)])
                s.add(z3.Implies(z3.And(self.kind_is(i,'->'),left_sub,self.kind_is(sub,'|')),
                    z3.And(z3.Not(self.child_kind(sub,'left','&')),
                           z3.Not(self.child_kind(sub,'right','&')))))
                s.add(z3.Implies(z3.And(self.kind_is(i,'->'),right_sub,self.kind_is(sub,'&')),
                    z3.And(z3.Not(self.child_kind(sub,'left','|')),
                           z3.Not(self.child_kind(sub,'right','|')))))
        if consequent:
            and0=z3.Int('named_And0')
            s.add(and0>=0,and0<n)
            s.add(_or(z3.And(and0==j,self.kind_is(j,'&')) for j in range(n)))
            s.add(_or(z3.And(and0==j,
                z3.Or(z3.And(child_ap(j,'left',1),child_ap(j,'right',2)),
                      z3.And(child_ap(j,'left',2),child_ap(j,'right',1)))) for j in range(1,n)))
            self.weak_and0=and0
        for i in range(1,n-1):
            lhs=z3.Or(child_ap(i,'left',0),
                _or(z3.And(self.left[i]==j,self.kind_is(j,'&'),child_ap(j,'left',0)) for j in range(1,i)))
            if consequent:
                rhs=z3.Or(self.right[i]==and0,
                    _or(z3.And(self.right[i]==j,self.kind_is(j,'|'),self.left[j]==and0) for j in range(1,i)))
                rhs=z3.And(rhs,_or(z3.And(self.right[i]==j,desc[j][k],and0==k)
                    for j in range(i) for k in range(j+1)))
            else:
                rhs=z3.Or(child_ap(i,'right',1),
                    _or(z3.And(self.right[i]==j,self.kind_is(j,'|'),child_ap(j,'left',1)) for j in range(1,i)))
            s.add(z3.Implies(self.left[n-1]==i,z3.And(lhs,rhs)))

    def witness(self, model: z3.ModelRef) -> dict:
        nodes=[]
        for i in range(self.size):
            row={'id':i,'label':self.labels[model.eval(self.kind[i]).as_long()]}
            if row['label'] in UNARY+BINARY:row['left']=model.eval(self.left[i]).as_long()
            if row['label'] in BINARY:row['right']=model.eval(self.right[i]).as_long()
            nodes.append(row)
        result={'nodes':nodes,'root':self.size-1,'size':self.size,'binaryNodes':sum(x['label'] in BINARY for x in nodes)}
        if hasattr(self,'repair_names'):
            names={key:model.eval(value).as_long() for key,value in self.repair_names.items()}
            result['namedNodes']=names
            result['keptEdges']=sum(names[b] in [nodes[names[a]].get('left'),nodes[names[a]].get('right')]
                                    for a,b in self.repair_edges)
        if hasattr(self,'weak_and0'):
            result['namedNodes']={'And0':model.eval(self.weak_and0).as_long()}
        return result


def evaluate_witness(task: Task, witness: dict) -> bool:
    nodes=witness['nodes']
    if not nodes or len(nodes)>task.B or sum(x['label'] in BINARY for x in nodes)>task.b:
        return False
    allowed={f'x{a}' for a in range(task.ap)} | set(task.operators)
    if any(node['id']!=i or node['label'] not in allowed for i,node in enumerate(nodes)):
        return False
    def children(i):
        node=nodes[i]
        return ([node['left']] if node['label'] in UNARY else
                [node['left'],node['right']] if node['label'] in BINARY else [])
    if any(not 0<=child<i for i in range(len(nodes)) for child in children(i)):
        return False
    def descendants(i):
        found={i}
        for child in children(i):found.update(descendants(child))
        return found
    if len(descendants(len(nodes)-1))!=len(nodes):return False
    if len({x['label'] for x in nodes if x['label'].startswith('x')}) != sum(x['label'].startswith('x') for x in nodes):
        return False
    if task.category=='plain':
        pass
    elif task.category=='nnf_template':
        if nodes[-1]['label']!='G':return False
        if 'n.l in Literal' in task.custom and any(n['label']=='!' and
                not nodes[n['left']]['label'].startswith('x') for n in nodes):return False
    elif task.category=='required':
        if nodes[-1]['label']!='G':return False
        for prop in re.findall(r'x(\d+)\s+in\s+root\.\*\(l\+r\)',task.custom):
            if not any(n['label']==f'x{prop}' for n in nodes):return False
        if 'root.l in Imply' in task.custom:
            implication=nodes[-1]['left']
            if nodes[implication]['label']!='->' or nodes[nodes[implication]['right']]['label']!='F':return False
        for node in nodes:
            if node['label'] in BINARY:
                left={i for i in descendants(node['left']) if nodes[i]['label'].startswith('x')}
                right={i for i in descendants(node['right']) if nodes[i]['label'].startswith('x')}
                if left & right:return False
    elif task.category=='repair':
        ra='G0' in task.custom
        names=witness.get('namedNodes',{})
        labels=({'And0':'&','F0':'F','G0':'G','Neg0':'!','x0':'x0','x2':'x2'} if ra else
                {'And0':'&','F0':'F','F1':'F','x0':'x0','x1':'x1'})
        if set(names)!=set(labels) or len(set(names.values()))!=len(names):return False
        if any(not 0<=idx<len(nodes) or nodes[idx]['label']!=labels[name] for name,idx in names.items()):return False
        if nodes[-1]['label']!='&':return False
        if any(n['label'] in BINARY and n['left']==n['right'] for n in nodes):return False
        for i,node in enumerate(nodes):
            if node['label'].startswith('x'):continue
            parents=sum(i in children(j) for j in range(i+1,len(nodes)))
            if parents>1:return False
        if not ra and any(n['label']=='!' and not nodes[n['left']]['label'].startswith('x') for n in nodes):return False
        edges=([('And0','G0'),('G0','Neg0'),('Neg0','x2'),('And0','F0'),('F0','x0')] if ra else
               [('And0','F0'),('F0','x0'),('And0','F1'),('F1','x1')])
        if witness.get('keptEdges')!=sum(names[b] in children(names[a]) for a,b in edges):return False
    elif task.category.startswith('weakening_'):
        consequent=task.category=='weakening_b3'
        if nodes[-1]['label']!='G' or nodes[nodes[-1]['left']]['label']!='->':return False
        imp=nodes[nodes[-1]['left']]
        for node in nodes:
            if node['label']!='->':continue
            for side in ('left','right'):
                child=nodes[node[side]]
                if child['label'] not in {'&','|','!'} and not child['label'].startswith('x'):return False
                if child['label']=='!' and not nodes[child['left']]['label'].startswith('x'):return False
            for i in descendants(node['left']):
                if nodes[i]['label']=='|' and any(nodes[c]['label']=='&' for c in children(i)):return False
            for i in descendants(node['right']):
                if nodes[i]['label']=='&' and any(nodes[c]['label']=='|' for c in children(i)):return False
        left=nodes[imp['left']]
        if not (left['label']=='x0' or left['label']=='&' and nodes[left['left']]['label']=='x0'):return False
        right=nodes[imp['right']]
        if consequent:
            names=witness.get('namedNodes',{})
            if set(names)!={'And0'}:return False
            and0=names['And0']
            if nodes[and0]['label']!='&' or {nodes[c]['label'] for c in children(and0)}!={'x1','x2'}:return False
            if and0 not in descendants(imp['right']):return False
            if not (imp['right']==and0 or right['label']=='|' and right['left']==and0):return False
        elif not (right['label']=='x1' or right['label']=='|' and nodes[right['left']]['label']=='x1'):
            return False
    else:return False
    for trace,expect in [(x,True) for x in task.positive]+[(x,False) for x in task.negative]:
        val=[]
        for node in nodes:
            label=node['label']
            if label.startswith('x'):
                row=[state[int(label[1:])] for state in trace.states]
            elif label=='!':row=[not v for v in val[node['left']]]
            elif label=='X':row=[val[node['left']][trace.next(p)] for p in range(len(trace.states))]
            elif label=='F':row=[any(val[node['left']][q] for q in trace.future(p)) for p in range(len(trace.states))]
            elif label=='G':row=[all(val[node['left']][q] for q in trace.future(p)) for p in range(len(trace.states))]
            elif label=='&':row=[a and b for a,b in zip(val[node['left']],val[node['right']])]
            elif label=='|':row=[a or b for a,b in zip(val[node['left']],val[node['right']])]
            elif label=='->':row=[not a or b for a,b in zip(val[node['left']],val[node['right']])]
            else:return False
            val.append(row)
        if val[-1][0]!=expect:return False
    return True


def check_size(task: Task, size: int, output: Path, timeout_ms: int, kept_at_least: int = 0) -> dict:
    output.mkdir(parents=True,exist_ok=True)
    started=time.monotonic()
    encoding=ExactEncoding(task,size,kept_at_least)
    query=encoding.solver.to_smt2()
    with gzip.open(output/'query.smt2.gz','wt',compresslevel=6) as f:f.write(query)
    encoding.solver.set(timeout=timeout_ms)
    result=encoding.solver.check()
    record={'size':size,'keptAtLeast':kept_at_least,'status':str(result),
            'wallSec':time.monotonic()-started,'querySha256':hashlib.sha256(query.encode()).hexdigest(),
            'z3Version':z3.get_version_string(),'reasonUnknown':encoding.solver.reason_unknown() if result==z3.unknown else ''}
    if result==z3.sat:
        witness=encoding.witness(encoding.solver.model())
        if not evaluate_witness(task,witness):raise AssertionError('Independent concrete lasso verifier rejected SMT witness')
        if witness.get('keptEdges',0)<kept_at_least:raise AssertionError('Repair primary objective below required bound')
        (output/'witness.json').write_text(json.dumps(witness,indent=2)+'\n')
        record['witnessSha256']=hashlib.sha256((output/'witness.json').read_bytes()).hexdigest()
        record['keptEdges']=witness.get('keptEdges',0)
    (output/'record.json').write_text(json.dumps(record,indent=2)+'\n')
    return record
