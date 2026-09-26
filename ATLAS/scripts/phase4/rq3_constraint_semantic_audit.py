#!/usr/bin/env python3
"""Reproduce the E4 matched constraint-text/parser/analyzer inventory and audit table."""

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET


ATLAS=Path(__file__).resolve().parents[2]
REPO=ATLAS.parent
TABLE=ATLAS/'experiment_artifacts/2026-09-25/rq2-full-623/summary/rq2_full_623_paper_data.csv'
GENERATED=ATLAS/'generated/phase4-preflight/matched_u_free'
ORIGINAL=ATLAS/'benchmark'
TEST_CLASSES=('ConstraintSemanticAuditTest','ConstraintAutomataTests','MacroSearchTest','MacroDifferentialTest')

# Keys are hashes of actual comment-preserving TaskParser customConstraints,
# recorded from the frozen 623 files. Unknown text never inherits a category's verdict.
PROFILES={
    'e3b0c442':dict(name='无自定义结构约束',features='',identity='',objective='MinExpandedSize',
        semantics='仅有 matched 输入的运算符、B、b、轨迹语义；无自定义 Alloy 约束。',
        encoding='空 product constraint state；一般 DAG/成本/二元节点预算。',
        verifier='DagConstraintEvaluator 的接受态、结构预算与原始 lasso 轨迹。',
        code='RecognizedConstraintAnalyzer.kt:137,273;MacroAlloyModelBuilder.kt:90-156;FinalSolutionVerifier.kt:57-65'),
    '26a1c5cd':dict(name='Voting：根 G + NNF',features='OfficialVoting;NNF',identity='',objective='MinExpandedSize',
        semantics='根节点是 G；每个 Neg 的直接 l 孩子是 Literal。文件没有对 G 的直接孩子或整个子树禁止时序运算符。',
        encoding='RootOperatorAutomaton(G) × NnfAutomaton；G 根锚定，状态经所有 fiber 传递；无 PropositionalOnly。',
        verifier='根约束与 NNF 的 automaton 接受态；对展开 DAG 重新求状态。',
        code='RecognizedConstraintAnalyzer.kt:43-46,154-160;NnfAutomaton.kt:11-25;MacroAlloyModelBuilder.kt:108-112;FinalSolutionVerifier.kt:62-63'),
    '45efdf2a':dict(name='Voting：仅根 G',features='OfficialVoting',identity='',objective='MinExpandedSize',
        semantics='仅要求根节点为 G；被注释的 NNF 不生效。没有直接孩子或子树的时序禁令。',
        encoding='RootOperatorAutomaton(G)；G 根锚定，允许 G/F/X 等在子树中出现。',
        verifier='根约束 automaton 接受态。',
        code='RecognizedConstraintAnalyzer.kt:43-46,154-160;MacroAlloyModelBuilder.kt:108-112;FinalSolutionVerifier.kt:62-63'),
    '2d9df7af':dict(name='Peterson：响应 + x6',features='OfficialPeterson;NoSharedLiteralBranches;RequiredProposition(x6)',
        identity='NoSharedLiteralBranches',objective='MinExpandedSize',
        semantics='根 G，直接孩子 Imply，Imply 的直接右孩子 F；x6 在根子树中。任一节点左右分支的 Literal 后代集合不得相交；注释中的 x2 不生效。',
        encoding='RootOperator(G) × ResponseOuterShape × RequiredProposition(x6)；二元锚的左右可达 Literal 集不交。',
        verifier='展开 DAG 重算 product state、左右 Literal 后代集合及原始轨迹。',
        code='RecognizedConstraintAnalyzer.kt:35-41,142-153;OfficialArtifactAutomata.kt:5-20;MacroAlloyModelBuilder.kt:166-167;FinalSolutionVerifier.kt:62-90'),
    'd58a9f51':dict(name='Peterson：安全 + x2,x8',features='OfficialPeterson;NoSharedLiteralBranches;RequiredProposition(x2);RequiredProposition(x8)',
        identity='NoSharedLiteralBranches',objective='MinExpandedSize',
        semantics='根 G；x2 和 x8 在根子树中；任一节点左右分支的 Literal 后代集合不得相交。没有 Imply/F 形状要求。',
        encoding='RootOperator(G) × RequiredProposition(x2,x8)；二元锚左右可达 Literal 集不交。',
        verifier='展开 DAG 重算 product state、左右 Literal 后代集合及原始轨迹。',
        code='RecognizedConstraintAnalyzer.kt:35-41,142-153;RequiredPropositionAutomaton.kt:5-22;MacroAlloyModelBuilder.kt:166-167;FinalSolutionVerifier.kt:62-90'),
    '21281860':dict(name='Peterson：响应 + x6,x2',features='OfficialPeterson;NoSharedLiteralBranches;RequiredProposition(x6);RequiredProposition(x2)',
        identity='NoSharedLiteralBranches',objective='MinExpandedSize',
        semantics='根 G、直接 Imply/F 响应形状；x6 与 x2 在根子树；任一左右分支没有共同 Literal 后代。',
        encoding='RootOperator(G) × ResponseOuterShape × RequiredProposition(x6,x2)；二元锚的 Literal 后代交集为空。',
        verifier='展开 DAG 重算 product state、左右 Literal 后代集合及原始轨迹。',
        code='RecognizedConstraintAnalyzer.kt:35-41,142-153;OfficialArtifactAutomata.kt:5-20;MacroAlloyModelBuilder.kt:166-167;FinalSolutionVerifier.kt:62-90'),
    '3733f60a':dict(name='Robot RA：5 条旧边',features='OfficialRobotRA;Repair;NoDAGReuse;LeftNotEqualRight',
        identity='NoDAGReuse(excludeLiterals=true);LeftNotEqualRight',objective='Repair',old_edges=5,protected=6,
        semantics='one sig 指定 And0/F0/G0/Neg0 身份；根是某个 And。非 Literal 至多一个不同父节点；二元节点左右直接孩子不同。按保留的 5 条指定直接边数优先、再最小化根可达 DAG 大小。',
        encoding='可选 protected slots 保留名称；非空 fiber 隔离共享边界，空 fiber 才是直接边；kept 精确计数，repair 字典序目标。',
        verifier='展开 DAG 的父节点数、左右孩子身份和指定旧边计数；不独立证明求解器最优性。',
        code='RecognizedConstraintAnalyzer.kt:47-51,169-192;MacroAlloyModelBuilder.kt:158-170,237-244;MacroLearner.kt:123-159;FinalSolutionVerifier.kt:69-106'),
    '1a473c55':dict(name='Robot RR：4 条旧边 + NNF',features='OfficialRobotRR;Repair;NoDAGReuse;LeftNotEqualRight',
        identity='NoDAGReuse(excludeLiterals=true);LeftNotEqualRight',objective='Repair',old_edges=4,protected=5,
        semantics='one sig 指定 And0/F0/F1 身份；根是某个 And；非 Literal 至多一个不同父节点；二元左右直接孩子不同；Neg 直接孩子是 Literal。按 4 条指定直接边保留数优先、再最小化 DAG 大小。',
        encoding='可选 protected slots、NNF constraint state；非空/空 fiber 区分共享边界及直接旧边；repair 字典序目标。',
        verifier='展开 DAG 重算 NNF、父节点数、左右孩子身份和旧边计数。',
        code='RecognizedConstraintAnalyzer.kt:52-56,169-192;NnfAutomaton.kt:11-25;MacroAlloyModelBuilder.kt:158-170,237-244;FinalSolutionVerifier.kt:62-106'),
    '6793473a':dict(name='Weakening antecedent 模板',features='OfficialWeakeningAntecedent',identity='',objective='MinExpandedSize',
        semantics='root=G0 且 G0.l=Imply0；每个 Imply 的所有严格后代（不是仅直接孩子）限于 Literal/And/Or/Neg；其中每个 Neg 直接孩子须为 Literal；左子树任一 Or 的所有严格后代不得有 And，右子树任一 And 的所有严格后代不得有 Or；Imply0 左/右端点各有指定直接孩子备选。',
        encoding='WeakeningTemplateAutomaton 的 body、noAndBelowOr、noOrBelowAnd、端点备选状态；G 根锚定；名称在无 repair 目标时可作存在量词消去。',
        verifier='展开 DAG 重算完整模板状态与根接受态。',
        code='RecognizedConstraintAnalyzer.kt:57-70,161-168;OfficialArtifactAutomata.kt:23-101;MacroAlloyModelBuilder.kt:149-156;FinalSolutionVerifier.kt:62-63'),
    'a20f604f':dict(name='Weakening consequent 模板',features='OfficialWeakeningConsequent',identity='',objective='MinExpandedSize',
        semantics='与 antecedent 相同的全后代限制；Imply0 右端为名为 And0 的 And 或左孩子为 And0 的 Or；And0 的直接左右孩子是 x1、x2（顺序可交换），And0 的两条边位于右子树 subDAG。',
        encoding='WeakeningTemplateAutomaton 的 body、noAndBelowOr、noOrBelowAnd、exactAnd12 与右端备选状态；G 根锚定。',
        verifier='展开 DAG 重算完整模板状态与根接受态。',
        code='RecognizedConstraintAnalyzer.kt:71-86,161-168;OfficialArtifactAutomata.kt:23-101;MacroAlloyModelBuilder.kt:149-156;FinalSolutionVerifier.kt:62-63'),
}
EXPECTED_FULL_HASHES={
    'e3b0c442':'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    '1a473c55':'1a473c559fe6857a0353880925b32cc2275b8a1e9d70b904606e811afb5a9a19',
    '21281860':'21281860c5f6cc0bde50084cda9d9817440664e679750da612484f6b1f982da5',
    '26a1c5cd':'26a1c5cdf634c218b7ec6578b1e99d466faacef0ee46f3f0bf3df29e92cfa4f7',
    '2d9df7af':'2d9df7af7d8884e7e857e5f9673e811205ce8a9106b28ecf32780e8687dbbe5b',
    '3733f60a':'3733f60a5df184a1a381e400584e26e4a312f1424d294befcb81814046432891',
    '45efdf2a':'45efdf2ac6601915ba5a4a2cb7ae27bb967933be1a1beebd11b26b0af231a3cb',
    '6793473a':'6793473afd9b8a8ec3a6c146d3e2f3b76d3d7cedbb5603fd69c5a251adad7319',
    'a20f604f':'a20f604f9fd520d01e90555be5a5f8af73e8a77bc912cc2e9a0be57b84057f87',
    'd58a9f51':'d58a9f51f5c1bc20f0078de05342722a1bf972de07a8d4d11d550cf51af247a6',
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalized(text: str) -> str:
    clean=re.sub(r'/\*[\s\S]*?\*/|//[^\n]*|--[^\n]*',' ',text)
    token=re.compile(r'[A-Za-z_][A-Za-z_0-9]*|[0-9]+|->|[{}()\[\].:*+&|=~,-]')
    end=0;out=[]
    for match in token.finditer(clean):
        if clean[end:match.start()].strip():raise ValueError('Unrecognized constraint token')
        out.append(match.group());end=match.end()
    if clean[end:].strip():raise ValueError('Unrecognized constraint suffix')
    return ' '.join(out)


def write_csv(path: Path, rows: list[dict], fields: list[str]):
    with path.open('w',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=fields,extrasaction='ignore')
        writer.writeheader();writer.writerows(rows)


def run_inspector(rows: list[dict], matched_root: Path) -> list[dict]:
    cp=':'.join([str(ATLAS/'target/classes'),str(ATLAS/'lib/AlloyMax-1.0.3.jar'),
                 (ATLAS/'target/runtime-classpath.txt').read_text().strip()])
    with tempfile.TemporaryDirectory() as temp:
        manifest=Path(temp)/'cases.tsv'
        manifest.write_text(''.join(f"{r['task']}\t{r['B']}\t{r['b']}\n" for r in rows))
        completed=subprocess.run(['java','-Xmx4g','-cp',cp,
            'cmu.s3d.ltl.experiment.ConstraintSemanticAuditMain',str(matched_root),str(manifest)],
            cwd=ATLAS,capture_output=True,text=True,check=True)
    result=[json.loads(line) for line in completed.stdout.splitlines()]
    if len(result)!=len(rows) or [x['task'] for x in result]!=[x['task'] for x in rows]:
        raise ValueError('Batch parser/analyzer output does not match 623-case manifest')
    return result


def main(output: Path):
    output.mkdir(parents=True,exist_ok=True)
    subprocess.run(['mvn','-q','-Dtest='+','.join(TEST_CLASSES),'test','dependency:build-classpath',
                    '-Dmdep.outputFile=target/runtime-classpath.txt'],cwd=ATLAS,check=True)
    test_results={}
    for name in TEST_CLASSES:
        files=list((ATLAS/'target/surefire-reports').glob('TEST-*'+name+'.xml'))
        if len(files)!=1:raise ValueError('Missing or duplicate audit test report: '+name)
        root=ET.parse(files[0]).getroot()
        count={key:int(root.attrib[key]) for key in ('tests','failures','errors','skipped')}
        if count['failures'] or count['errors']:raise ValueError('Audit test failed: '+name)
        test_results[name]=count
    source=list(csv.DictReader(TABLE.open(newline='')))
    if len(source)!=623 or len({r['task'] for r in source})!=623:
        raise ValueError('Expected exactly 623 unique frozen E4 matched cases')
    matched_root=output/'inputs'
    for row in source:
        task=row['task'];original=ORIGINAL/task
        parts=original.read_text().split('---')
        operators=[x.strip() for x in parts[2].strip().split(',')]
        parts[2]='\n'+','.join(x for x in operators if x!='U')+'\n'
        adapted='---'.join(parts).encode()
        if sha(adapted)!=row['inputSha256']:
            raise ValueError('Regenerated matched input differs from frozen E4: '+task)
        frozen=GENERATED/task
        if frozen.exists() and frozen.read_bytes()!=adapted:
            raise ValueError('Existing generated matched input differs: '+task)
        destination=matched_root/task
        destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_bytes(adapted)
    inspected=run_inspector(source,matched_root)
    inspector_path=output/'parser_analyzer.jsonl'
    inspector_path.write_text(''.join(json.dumps(row,ensure_ascii=False,sort_keys=True)+'\n' for row in inspected))
    cases=[];groups={}
    for row,actual in zip(source,inspected):
        task=row['task'];matched=matched_root/task;original=ORIGINAL/task
        problems=[]
        if sha(matched.read_bytes())!=row['inputSha256']:problems.append('MATCHED_INPUT_SHA256')
        matched_parts=matched.read_text().split('---');original_parts=original.read_text().split('---')
        if len(matched_parts)!=len(original_parts) or len(matched_parts)<4:
            problems.append('ORIGINAL_MATCHED_SECTION_COUNT')
        else:
            for i,(left,right) in enumerate(zip(original_parts,matched_parts)):
                if i!=2 and left!=right:problems.append(f'ADAPTER_CHANGED_SECTION_{i}')
            old_ops=[x.strip() for x in original_parts[2].split(',')]
            new_ops=[x.strip() for x in matched_parts[2].split(',')]
            if new_ops!=[x for x in old_ops if x!='U']:problems.append('ADAPTER_CHANGED_OPERATORS_OTHER_THAN_U')
        raw=matched_parts[5].strip() if len(matched_parts)>5 else ''
        full_hash=sha(raw.encode());key=full_hash[:8]
        spec=PROFILES.get(key) if EXPECTED_FULL_HASHES.get(key)==full_hash else None
        if spec is None:problems.append('UNKNOWN_CONSTRAINT_TEXT')
        if actual.get('customText')!=raw:problems.append('TASKPARSER_CUSTOM_TEXT')
        if actual.get('parsedB')!=int(row['B']) or actual.get('B')!=int(row['B']) or actual.get('b')!=int(row['b']):
            problems.append('PARSER_B_OR_BUDGET')
        if not actual.get('supported'):problems.append('ANALYZER_UNSUPPORTED')
        if spec:
            if actual.get('features')!=spec['features']:problems.append('ANALYZER_FEATURES')
            if actual.get('identityConstraints')!=spec['identity']:problems.append('ANALYZER_IDENTITIES')
            if actual.get('objective')!=spec['objective']:problems.append('ANALYZER_OBJECTIVE')
            if actual.get('oldEdges','').count('->')!=spec.get('old_edges',0):problems.append('ANALYZER_REPAIR_EDGES')
            if len([x for x in actual.get('protectedIdentities','').split(';') if x])!=spec.get('protected',0):
                problems.append('ANALYZER_PROTECTED_IDENTITIES')
            if key in ('26a1c5cd','45efdf2a','2d9df7af','d58a9f51','21281860','6793473a','a20f604f'):
                if actual.get('requiredRootUnary')!='G':problems.append('ROOT_G_NOT_ANCHORED')
        case={'task':task,'family':row['family'],'B':row['B'],'b':row['b'],
              'inputSha256':row['inputSha256'],'constraintSha256':full_hash,
              'profile':spec['name'] if spec else '未知约束文本',
              'status':'UNRESOLVED' if spec is None else 'MISMATCH' if problems else 'EXACT_MATCH',
              'issues':';'.join(problems),'matchedPath':str(matched.relative_to(REPO)),
              'originalPath':str(original.relative_to(REPO)),
              'recognizedFeatures':actual.get('features',''),'identityConstraints':actual.get('identityConstraints',''),
              'protectedIdentities':actual.get('protectedIdentities',''),'oldEdges':actual.get('oldEdges','')}
        cases.append(case)
        group=groups.setdefault(full_hash,{'key':key,'raw':raw,'paths':[],'families':set(),'cases':[]})
        if group['raw']!=raw:raise ValueError('Constraint hash collision')
        group['paths'].append(str(matched.relative_to(REPO)))
        group['families'].add(row['family']);group['cases'].append(case)
    texts=output/'constraint_texts';texts.mkdir(exist_ok=True)
    profiles=[]
    for full_hash,group in sorted(groups.items(),key=lambda item:(item[1]['key']!='e3b0c442',item[1]['key'])):
        key=group['key'];spec=PROFILES.get(key)
        (texts/f'{key}.txt').write_text(group['raw']+'\n')
        statuses={case['status'] for case in group['cases']}
        status='MISMATCH' if 'MISMATCH' in statuses else 'UNRESOLVED' if 'UNRESOLVED' in statuses else 'EXACT_MATCH'
        profiles.append({'profile':spec['name'] if spec else '未知约束文本',
            'families':';'.join(sorted(group['families'])),'cases':len(group['cases']),
            'representativePath':group['paths'][0],'constraintSha256':full_hash,
            'rawText':group['raw'],'normalizedText':normalized(group['raw']),
            'sourceSemantics':spec['semantics'] if spec else '',
            'analyzerRecognition':spec['features'] if spec else '',
            'macroEncoding':spec['encoding'] if spec else '',
            'finalVerifier':spec['verifier'] if spec else '',
            'codeLocations':spec['code'] if spec else '',
            'status':status,'issues':';'.join(sorted({case['issues'] for case in group['cases'] if case['issues']}))})
    write_csv(output/'per_case.csv',cases,list(cases[0]))
    write_csv(output/'constraint_profiles.csv',profiles,list(profiles[0]))
    counts=collections.Counter(case['status'] for case in cases)
    family_status={}
    for family in sorted({case['family'] for case in cases}):
        subset=[c for c in cases if c['family']==family]
        family_status[family]='MISMATCH' if any(c['status']=='MISMATCH' for c in subset) else (
            'UNRESOLVED' if any(c['status']=='UNRESOLVED' for c in subset) else 'EXACT_MATCH')
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
    evidence={'cases':len(cases),'profiles':len(profiles),'statusCounts':dict(counts),
              'familyStatus':family_status,'sourceCommit':commit,'sourceTableSha256':sha(TABLE.read_bytes()),
              'inspectorClass':'cmu.s3d.ltl.experiment.ConstraintSemanticAuditMain',
              'inspectorJsonlSha256':sha(inspector_path.read_bytes()),
              'testResults':test_results,
              'codeSha256':{str(path.relative_to(REPO)):sha(path.read_bytes()) for path in [
                  ATLAS/'src/main/kotlin/cmu/s3d/ltl/samples2ltl/TaskParser.kt',
                  ATLAS/'src/main/kotlin/cmu/s3d/ltl/experiment/ConstraintSemanticAuditMain.kt',
                  ATLAS/'src/main/kotlin/cmu/s3d/ltl/learning/LTLLearner.kt',
                  ATLAS/'src/main/kotlin/cmu/s3d/ltl/macro/search/RecognizedConstraintAnalyzer.kt',
                  ATLAS/'src/main/kotlin/cmu/s3d/ltl/macro/search/MacroAlloyModelBuilder.kt',
                  ATLAS/'src/main/kotlin/cmu/s3d/ltl/macro/search/FinalSolutionVerifier.kt',
                  ATLAS/'src/main/kotlin/cmu/s3d/ltl/macro/constraint/OfficialArtifactAutomata.kt']},
              'negativeControl':'9 Voting constraints contain no temporal-child/subtree ban; 1 additional Voting input comments out NNF',
              'outOfScope':'CNF/DNF and generic NamedDirectChild/NamedReachability/NamedRoot are not present in these 623 E4 custom texts'}
    (output/'summary.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
    lines=['# RQ3 / E4 matched 约束语义审计','',
           f"逐题输入、适配、TaskParser 和 RecognizedConstraintAnalyzer 核对：**{len(cases)}/623**。",
           f"审计状态：{dict(counts)}。实际自定义文本有 **{len(profiles)-1}** 种；另有 485 题无自定义约束。",
           '', '| 实际 family | 题数 | 审计状态 |', '| --- | ---: | --- |']
    for family,status in family_status.items():
        lines.append(f"| {family} | {sum(c['family']==family for c in cases)} | {status} |")
    lines += ['', '## 实际出现的约束形式', '', '| 规范化文本标识 | 题数 | 来源文件 | 识别结果 | 状态 |',
              '| --- | ---: | --- | --- | --- |']
    for profile in profiles:
        key=profile['constraintSha256'][:8]
        lines.append(f"| `{key}` {profile['profile']} | {profile['cases']} | `{profile['representativePath']}` | `{profile['analyzerRecognition'] or 'none'}` | {profile['status']} |")
    lines += ['', '完整原文、规范化 token、语义、编码与 verifier 位置见 `constraint_profiles.csv`；',
              '每题输入 SHA、文件路径及 analyzer 实测结果见 `per_case.csv`；真实 Kotlin parser/analyzer 的完整逐题输出另存 `parser_analyzer.jsonl`。原文另存 `constraint_texts/`。',
              '', 'Voting 的真实约束仅为 `root in G`，9 题另有生效的 NNF；',
              '文件**没有**“直接孩子无时序运算符”或“整个子树无时序运算符”约束。',
              '测试用 `G(F(x0))` 证实 Macro 接受时序后代，并用 `G(!(F(x0)))` 区分有无 NNF。',
              '', 'ATLAS 的 `childrenOf[n] = n.^(l+r)` 是全部严格后代；`childrenAndSelfOf[n] = n.*(l+r)` 包含自身。',
              'Weakening 的 operator、NNF 局部规则和 CNF/DNF 禁止嵌套规则均须按相应量词范围解释。',
              'Macro 模板状态的 `body`、`containsAnd/Or`、`noAndBelowOr/noOrBelowAnd` 与该传递语义对应。',
              '', 'Robot repair 的 `one sig` 名称允许不在根子树；Macro 用可选 protected slot 表示。',
              '未使用的命名节点可在 ATLAS-B 的非根部分补齐：RR 的 F0/F1 指向 Literal，And0',
              '可指向两个不同 Literal；RA 的 G0/Neg0/F0 可指向 Literal，And0 可指向两个',
              '不同 Literal。它们不会改变根可达大小或旧边保留数；`DAGNode = experimentReach + Literal + named`',
              '给这些节点保留了 scope。非空 fiber 只在命名节点之间插入匿名一元节点，',
              '因此只有空 fiber 构成指定的直接旧边。',
              '结构预算 `K=min(B,p+3b+2)` 只给 Literal、二元节点、受保护节点和共享一元节点留锚位；',
              '其余一元链进入 fiber。根 G 无父节点，可从根 fiber 移到根锚，不改变可表示公式、',
              '共享关系或大小；`MacroConstraintPlan.kt:56`、`AnchorExtractor.kt:9-40` 和',
              '`MacroAlloyModelBuilder.kt:22-27,103-112` 给出这一路径。',
              'NoDAGReuse 的 `lone n.~(l+r)` 计算不同父节点身份：两个空 port 来自同一父节点仍只算一个；',
              '非空 fiber 的每个 port 会新建一元链头，因此可产生新的父节点。Macro 编码同时检查',
              '非空 ingress 数、空 ingress 的不同 src 数与二者不共存；`no l & r` 则要求二元左右',
              '展开后的直接孩子不是同一节点。最终 verifier 直接在展开 DAG 上复核父节点数与左右孩子身份。',
              '', 'FinalSolutionVerifier 重算的是已识别 plan 的自动机状态、身份约束和 repair 旧边计数，',
              '**不重新解释原始 Alloy 约束文本，也不独立证明优化最优性**。文本到 plan 的等价性由本表、',
              '完整块匹配和源码分支核对；E4 求解器结果一致本身不构成该证明。',
              '', '## 重点核查的其余代码分支', '',
              '| 条件 | 623 题中实际出现 | 语义与实现 |', '| --- | --- | --- |',
              '| NNF | Voting 9 题、Robot RR 10 题 | `Neg.l` 必须是**直接** Literal；`NnfAutomaton` 逐层传递无效状态，最终重新求根状态。 |',
              '| RequiredProposition | Peterson 30 题 | 指定 xN 必须在根的包含自身的子树中；自动机 OR 传播出现位，最终重新求根状态。 |',
              '| CNF/DNF | 0 题 | 原通用文本的 `childrenOf[n]` 是**全部严格后代**，不是直接孩子；CNF 禁 And 位于 Or 后代，DNF 对偶，均要求命题节点与直接原子否定。`CnfAutomaton`/`DnfAutomaton` 传播子树标志；此项仅作为通用代码审查，不计入 E4 结论。 |',
              '| 通用 named direct/reach/root | 0 题 | 通用 analyzer 编译成 `NamedDirectChild`（指定 port 的空 fiber）、`NamedReachability`（锚图 `^graph` 严格后代）、`NamedRoot`（空 root fiber）；verifier 在展开 DAG 上分别检查直接孩子、图可达与根身份。Weakening 的特殊模板另以状态表示存在命名节点。 |',
              '| 通用 G(Prop)、响应 template | 0 题 | `FixedTemplateAutomaton` 的通用分支未被 E4 采用；E4 的 Peterson 响应与 Weakening 模板走各自的完整块分支。 |',
              '| NoDAGReuse / LeftNotEqualRight / repair | Robot 20 题 | 分别按非 Literal 的不同父节点、二元节点的直接左右孩子身份、指定旧边直接连接的保留数检查；上文给出编码与 verifier 对应关系。 |',
              '', '通用分支源码在 `RecognizedConstraintAnalyzer.kt:215-249`、',
              '`CnfAutomaton.kt`、`DnfAutomaton.kt` 和 `MacroAlloyModelBuilder.kt:158-170`；',
              '通用分支的测试结果不冒充 E4 实际使用。',
              '', f'测试：{test_results}。',
              '复现：从仓库根目录执行 `python3 ATLAS/scripts/phase4/rq3_constraint_semantic_audit.py --output <新目录>`；',
              '脚本会先运行相关 Kotlin 测试并构建 classpath，再逐题调用真实 parser/analyzer。']
    if all(status=='EXACT_MATCH' for status in family_status.values()):
        lines += ['', '**结论：这 623 个 E4 matched 案例实际使用的结构约束，已逐项核对为 EXACT_MATCH。**']
    else:
        lines += ['', '**结论：仍有 MISMATCH/UNRESOLVED，不能声称实验约束语义已全部核对一致。**']
    (output/'REPORT.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'cases':len(cases),'profiles':len(profiles),'statusCounts':dict(counts),
                      'familyStatus':family_status},ensure_ascii=False,indent=2))
    if counts.get('MISMATCH',0) or counts.get('UNRESOLVED',0):raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    main(args.output.resolve())
