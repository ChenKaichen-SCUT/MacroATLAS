#!/usr/bin/env python3
"""Combine frozen 200-case and 423-case same-scope translations into all 623 cases."""
import argparse
import collections
import csv
import hashlib
import json
import pathlib
import statistics

MODES = ('atlas-b', 'macro')
SUCCESS = 'TRANSLATED_ONLY'


def load(path):
    return json.loads(pathlib.Path(path).read_text())


def table(path):
    with pathlib.Path(path).open(newline='') as stream:
        return list(csv.DictReader(stream))


def sha(path):
    digest = hashlib.sha256()
    with pathlib.Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def check(value, message):
    if not value:
        raise ValueError(message)


def key(row):
    return row['batch'], row['task']


def records(directory):
    plan = load(directory / 'plan.json')
    check(sha(directory / 'plan.json') == (directory / 'plan.sha256').read_text().split()[0],
          'Plan checksum changed: ' + str(directory))
    return plan, load(directory / 'state.json')


def status(old, new):
    old_plan, old_state = records(old)
    new_plan, new_state = records(new)
    check(len(old_plan['jobs']) == 200 and len(new_plan['jobs']) == 423,
          'Expected frozen 200 cases and complement of 423 cases')
    totals = collections.Counter()
    modes = {mode: collections.Counter() for mode in MODES}
    for directory, plan in ((old, old_plan), (new, new_plan)):
        for job in plan['jobs']:
            complete = 0
            for mode in MODES:
                record = directory / 'jobs' / job['jobId'] / mode / 'record.json'
                if record.exists():
                    complete += 1
                    modes[mode][load(record)['status']] += 1
            if complete == 2:
                totals['pairs'] += 1
    print('RQ2 full same-scope: pairs %d/623 | ATLAS-B %d/623 | MacroATLAS %d/623 | '
          'old=%s | extension=%s' % (totals['pairs'], sum(modes['atlas-b'].values()),
                                     sum(modes['macro'].values()), old_state['status'],
                                     new_state['status']))
    for mode in MODES:
        print(mode, dict(modes[mode]))


def dist(values):
    values = sorted(values)
    return {'n': len(values), 'median': statistics.median(values) if values else None,
            'min': values[0] if values else None, 'max': values[-1] if values else None}


def group(rows):
    complete = [row for row in rows if row['pairedTranslated'] == 'True']
    return {'cases': len(rows), 'completePairs': len(complete),
            'atlasTranslated': sum(row['atlasStatus'] == SUCCESS for row in rows),
            'macroTranslated': sum(row['macroStatus'] == SUCCESS for row in rows),
            'C_V': dist(float(row['C_V']) for row in complete),
            'C_C': dist(float(row['C_C']) for row in complete),
            'macroFewerVars': sum(float(row['C_V']) > 1 for row in complete),
            'macroFewerClauses': sum(float(row['C_C']) > 1 for row in complete)}


def write_csv(path, rows):
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def format_number(value, digits=3):
    return '—' if value is None else f'{value:.{digits}f}'


def markdown(result):
    o = result['overall']
    a, m = result['statuses']['atlas-b'], result['statuses']['macro']
    macro_only = sum(item['cases'] for item in result['statusPairs']
                     if item['atlas'] != SUCCESS and item['macro'] == SUCCESS)
    atlas_only = sum(item['cases'] for item in result['statusPairs']
                     if item['atlas'] == SUCCESS and item['macro'] != SUCCESS)
    lines = [
        '# RQ2：全部 623 题相同展开大小上界的 CNF 翻译结果', '',
        '本报告只使用同范围翻译实验：复用已完成的 200 题，新增翻译其余 423 题。'
        '每题的 ATLAS-B 与 MacroATLAS 使用相同输入、`B`、`b`、运算符、约束及'
        '展开大小上界 `s`；每个“算法 × 案例 × s”仅发射一次，翻译到 CNF 后停止，'
        '**不运行 MaxSAT**。早期各算法实际搜索最大模型的 623 题测量不纳入本报告。', '',
        f"覆盖：**{o['cases']}/623** 题、**1246/1246** 条一次性记录；双方均完成翻译 "
        f"**{o['completePairs']}/623** 对。ATLAS-B 完成 **{o['atlasTranslated']}/623**，"
        f"MacroATLAS 完成 **{o['macroTranslated']}/623**。", '',
        '## 总体结果', '',
        '| 指标 | 完整配对数 | 逐题比值中位数 | Macro 更少的配对数 |',
        '| --- | ---: | ---: | ---: |',
        f"| `C_V=Vars_ATLAS-B/Vars_Macro` | {o['completePairs']} | "
        f"{format_number(o['C_V']['median'])} | {o['macroFewerVars']}/{o['completePairs']} |",
        f"| `C_C=Clauses_ATLAS-B/Clauses_Macro` | {o['completePairs']} | "
        f"{format_number(o['C_C']['median'])} | {o['macroFewerClauses']}/{o['completePairs']} |", '',
        '比值大于 1 才表示 Macro 的对应后端 CNF 指标更小。中位数只取双方成功翻译的'
        '配对；超时、报错及中断不能当作压缩成功，也不能把完整配对中位数无条件'
        '外推到失败案例。AlloyMax 回调给出总变量数和总 clause 数，没有可靠的 hard/soft 拆分。', '',
        '## 翻译状态', '',
        '| 方法 | TRANSLATED_ONLY | TRANSLATION_TIMEOUT | TRANSLATION_ERROR | 其他 |',
        '| --- | ---: | ---: | ---: | ---: |',
        f"| ATLAS-B | {a.get(SUCCESS, 0)} | {a.get('TRANSLATION_TIMEOUT', 0)} | "
        f"{a.get('TRANSLATION_ERROR', 0)} | {sum(a.values())-a.get(SUCCESS,0)-a.get('TRANSLATION_TIMEOUT',0)-a.get('TRANSLATION_ERROR',0)} |",
        f"| MacroATLAS | {m.get(SUCCESS, 0)} | {m.get('TRANSLATION_TIMEOUT', 0)} | "
        f"{m.get('TRANSLATION_ERROR', 0)} | {sum(m.values())-m.get(SUCCESS,0)-m.get('TRANSLATION_TIMEOUT',0)-m.get('TRANSLATION_ERROR',0)} |", '',
        f'仅 MacroATLAS 完成翻译 **{macro_only}** 题，仅 ATLAS-B 完成翻译 **{atlas_only}** 题；'
        '全部失败类型及逐题记录在 CSV/JSON 中保留。', '',
        '## 分组结果', '',
        '| 组别 | 题数 | 完整配对 | `C_V` 中位 | `C_C` 中位 | Macro 变量更少 | Macro clause 更少 |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: |',
    ]
    for name, item in result['byConstraint'].items():
        lines.append(f"| {name} | {item['cases']} | {item['completePairs']} | "
                     f"{format_number(item['C_V']['median'])} | {format_number(item['C_C']['median'])} | "
                     f"{item['macroFewerVars']}/{item['completePairs']} | "
                     f"{item['macroFewerClauses']}/{item['completePairs']} |")
    for name, item in result['byFamily'].items():
        lines.append(f"| `{name}` | {item['cases']} | {item['completePairs']} | "
                     f"{format_number(item['C_V']['median'])} | {format_number(item['C_C']['median'])} | "
                     f"{item['macroFewerVars']}/{item['completePairs']} | "
                     f"{item['macroFewerClauses']}/{item['completePairs']} |")
    lines += ['', '不同 `s` 的案例构成不同；下表只是覆盖率与描述性统计。', '',
              '| 展开大小上界 `s` | 题数 | 完整配对 | `C_V` 中位 | `C_C` 中位 |',
              '| ---: | ---: | ---: | ---: | ---: |']
    for scope, item in result['byScope'].items():
        lines.append(f"| {scope} | {item['cases']} | {item['completePairs']} | "
                     f"{format_number(item['C_V']['median'])} | {format_number(item['C_C']['median'])} |")
    lines += ['', '## 搜索范围与解释边界', '',
              f"结构预算 `B/K` 在全部 623 题上的中位数为 "
              f"**{format_number(result['B_over_K']['median'])}**；"
              f"有 **{result['KLessThanB']}/623** 题满足 `K<B`。"
              '这只是预算比，不等于实际 CNF 压缩比。', '',
              '原 200 题的 `s` 按冻结计划保持不变；剩余 423 题以固定 SHA-256 顺序'
              '分配旧协议的 5/7/5/9/5/11/5/15 候选循环，再限制 `s≤B`。'
              '其中 `B<5` 的案例使用 `s=B`，因此本轮包含旧抽样中没有的较小 scope。'
              '每题只测一个 `s`，按 scope 分组的差别不能解释为同一题随 `s` 增长的曲线。'
              '双方的 Alloy atom universe 可以不同，因此这里比较的是相同展开大小上界下的'
              '完整表示及翻译结果，不能把差异只归因于 unary quotient。', '',
              'repair 在两算法中都保留相同硬约束与最小公式大小目标，省略保留旧边的主目标；'
              '因此 repair 的 CNF 数字不能代表正式 E4 词典序 repair 求解的全部成本。'
              '本实验不测 SAT/UNSAT、最优公式或求解时间。', '',
              '## 结论', '',
              (f"在全部 623 题中的 {o['completePairs']} 个可比配对上，MacroATLAS 的后端总变量"
               + ('通常更少' if o['C_V']['median'] is not None and o['C_V']['median'] > 1 else '没有呈现总体中位压缩')
               + '，后端总 clause'
               + ('通常更少' if o['C_C']['median'] is not None and o['C_C']['median'] > 1 else '没有呈现总体中位压缩')
               + '。请结合上表的家族差异、失败题及翻译覆盖率解读总体中位数；'
               '同范围 CNF 规模本身不能证明端到端求解速度或最优性。'), '',
              '## 复核文件', '',
              '- `rq2_full_623_paper_data.csv`：623 条配对数据、逐题状态、`B/b/K/q/s`、CNF 计数与可用比值。',
              '- `rq2_full_623_per_run.csv`：1246 条方法记录及一次性尝试、错误和翻译时间。',
              '- `rq2_full_623_summary.json`：总体、约束组、家族、scope、状态和来源哈希。',
              '- 原 200 题和新增 423 题的计划、输入哈希、逐次 `started.json`/`record.json`、'
              '模型及翻译输出分别保留在两活动目录。', '',
              f"来源计划 SHA-256：原 200 题 `{result['provenance']['oldPlanSha256']}`；"
              f"新增 423 题 `{result['provenance']['newPlanSha256']}`。", '']
    return '\n'.join(lines)


def summarize(old, new):
    old_plan, old_state = records(old)
    new_plan, new_state = records(new)
    check(old_state['status'] == new_state['status'] == 'COMPLETE', 'Campaign still incomplete')
    check(len(old_plan['jobs']) == 200 and len(new_plan['jobs']) == 423,
          'Expected 200 old and 423 new cases')
    check(old_plan['sourceSha256'] == new_plan['sourceSha256'], 'Source table hash differs')
    check(new_plan['completedPlan']['sha256'] == sha(old / 'plan.json'),
          'Complement does not reference frozen 200-case plan')
    source = table(new_plan['sourceCsv'])
    source_keys = {key(row) for row in source}
    check(len(source) == len(source_keys) == 623 and sha(new_plan['sourceCsv']) == new_plan['sourceSha256'],
          'Frozen E4 source differs')
    plans = [('frozen200', old, old_plan), ('remaining423', new, new_plan)]
    all_runs, all_pairs = [], []
    seen = set()
    for label, directory, plan in plans:
        runs = table(directory / 'summary/rq2_same_scope_per_run.csv')
        pairs = table(directory / 'summary/rq2_same_scope_paper_data.csv')
        check(len(runs) == len(plan['jobs']) * 2 and len(pairs) == len(plan['jobs']),
              'Summary row count differs: ' + label)
        indexed = {(row['batch'], row['task'], row['method']): row for row in runs}
        pair_index = {key(row): row for row in pairs}
        check(len(indexed) == len(runs) and len(pair_index) == len(pairs), 'Duplicate keys: ' + label)
        for job in plan['jobs']:
            k = key(job)
            check(k not in seen and k in source_keys, 'Duplicate or unknown case: ' + str(k))
            seen.add(k)
            pair = pair_index[k]
            check(int(pair['scope']) == job['scope'] and pair['inputSha256'] == job['inputSha256'],
                  'Case scope or input hash differs: ' + str(k))
            pair = {'campaign': label, **pair}
            details = {}
            for mode in MODES:
                run = indexed[k + (mode,)]
                recpath = directory / 'jobs' / job['jobId'] / mode / 'record.json'
                started = directory / 'jobs' / job['jobId'] / mode / 'started.json'
                check(recpath.exists() and started.exists(), 'Missing raw record: ' + str(recpath))
                rec, marker = load(recpath), load(started)
                check(marker['attempt'] == rec['attempt'] == 1 and marker['solverInvoked'] is False and
                      rec['solverInvoked'] is False and marker['scope'] == job['scope'] and
                      run['status'] == rec['status'] and run['attempt'] == '1' and
                      run['solverInvoked'] == 'False', 'Raw record differs: ' + str(recpath))
                for field in ('vars', 'backendTotalClauses'):
                    check(run[field] == (str(rec[field]) if rec[field] is not None else ''),
                          'CNF count differs: ' + str(recpath))
                details[mode] = rec
                all_runs.append({'campaign': label, **run})
            a, m = details['atlas-b'], details['macro']
            both = a['status'] == m['status'] == SUCCESS
            check((pair['pairedTranslated'] == 'True') == both and
                  pair['atlasStatus'] == a['status'] and pair['macroStatus'] == m['status'],
                  'Pair status differs: ' + str(k))
            if both:
                check(abs(float(pair['C_V']) - a['vars']/m['vars']) < 1e-9 and
                      abs(float(pair['C_C']) - a['backendTotalClauses']/m['backendTotalClauses']) < 1e-9,
                      'Pair ratios differ: ' + str(k))
            else:
                check(pair['C_V'] == pair['C_C'] == '', 'Failed pair assigned ratio: ' + str(k))
            all_pairs.append(pair)
    check(seen == source_keys and len(all_runs) == 1246 and len(all_pairs) == 623,
          'Not all 623 source cases are covered exactly once')
    all_pairs.sort(key=lambda row: (row['batch'], row['task']))
    all_runs.sort(key=lambda row: (row['batch'], row['task'], row['method']))
    summary = {'cases': 623, 'runs': 1246, 'attemptsPerCaseMethodScope': 1,
               'overall': group(all_pairs),
               'statuses': {mode: dict(collections.Counter(row['status'] for row in all_runs
                        if row['method'] == mode)) for mode in MODES},
               'statusPairs': [{'atlas': a, 'macro': m, 'cases': count} for (a, m), count
                        in sorted(collections.Counter((row['atlasStatus'], row['macroStatus'])
                                                      for row in all_pairs).items())],
               'byConstraint': {label: group([row for row in all_pairs if
                    (int(row['qStates']) == 1) == (label == '无约束 q=1')])
                    for label in ('无约束 q=1', '受约束 q>1')},
               'byFamily': {family: group([row for row in all_pairs if row['family'] == family])
                    for family in sorted({row['family'] for row in all_pairs})},
               'byScope': {str(scope): group([row for row in all_pairs if int(row['scope']) == scope])
                    for scope in sorted({int(row['scope']) for row in all_pairs})},
               'byBinaryBudget': {str(b): group([row for row in all_pairs if int(row['b']) == b])
                    for b in sorted({int(row['b']) for row in all_pairs})},
               'B_over_K': dist(float(row['B_over_K']) for row in all_pairs),
               'KLessThanB': sum(int(row['K']) < int(row['B']) for row in all_pairs),
               'provenance': {'sourceSha256': new_plan['sourceSha256'],
                              'oldPlanSha256': sha(old / 'plan.json'),
                              'newPlanSha256': sha(new / 'plan.json'),
                              'oldCommit': old_plan['commit'], 'newCommit': new_plan['commit'],
                              'oldCases': 200, 'newCases': 423}}
    output = new / 'summary'
    output.mkdir(exist_ok=True)
    write_csv(output / 'rq2_full_623_paper_data.csv', all_pairs)
    write_csv(output / 'rq2_full_623_per_run.csv', all_runs)
    (output / 'rq2_full_623_summary.json').write_text(json.dumps(summary, ensure_ascii=False,
                                                               indent=2, sort_keys=True) + '\n')
    (output / 'RQ2_FULL_623_REPORT.zh-CN.md').write_text(markdown(summary))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print('REPORT', output / 'RQ2_FULL_623_REPORT.zh-CN.md')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('status', 'summary'))
    parser.add_argument('--old', type=pathlib.Path, required=True)
    parser.add_argument('--new', type=pathlib.Path, required=True)
    args = parser.parse_args()
    if args.command == 'status':
        status(args.old, args.new)
    else:
        summarize(args.old, args.new)


if __name__ == '__main__':
    main()
