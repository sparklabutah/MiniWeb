"""Publish the follow-up verifier repairs and authorized Stale review queue."""
import argparse
import collections
import csv
import difflib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from annotation.macros import all_canonical, canon, entry
from annotation.quality import engine_hash, source_hash


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', default='data/verifier_audit_hardening_2026-09-23')
    parser.add_argument('--publish', action='store_true')
    parser.add_argument('--auth-state', default='/tmp/miniweb-review-browser.json')
    args = parser.parse_args()
    out = ROOT / args.audit
    baseline, plan = read(out/'baseline.json'), read(out/'plan.json')
    checks = {r['key']: r for r in read(out/'final/automated.json')}
    interface = read(out/'interface_checks.json')
    targeted = read(out/'targeted_probes.json')
    fresh = read(out/'fresh_walks.json')
    stale = {r['key']: r for r in read(out/'stale_marks.json')}
    assert len(baseline) == len(checks) == 407 and len(interface) == 404
    assert all(r['passed'] == r['expected'] for r in targeted)
    assert all(r['passed'] for r in fresh.values())
    assert all(r['engine_hash'] == engine_hash() for tests in interface.values() for r in tests.values())
    (out/'tasks').mkdir(exist_ok=True)
    records, payloads, preservation = [], {}, []
    for key, before in baseline.items():
        directory = ROOT/'data/annotations'/key
        task = read(directory/'task.json')
        macros = read(directory/'verifier.json')['macros'] if before['verifier'] else {}
        row, amendment = checks[key], plan.get(key)
        previous = task.get('ai_review', {})
        recommendation = ('suggest_delete' if key in stale else 'repaired' if amendment
                          else before['task']['ai_review']['recommendation'])
        source = row.get('source')
        positive = interface.get(key, {}).get(source, {}).get('passed')
        issues = list(previous.get('issues', [])) if key in stale else []
        if key not in stale:
            assert positive is True, (key, source, 'retained positive failed')
            assert not row.get('unexpected'), (key, row['unexpected'])
        else:
            assert task.get('review_tag', {}).get('tag') == 'stale', key
        allowed = {'ai_review'} | ({'review_tag'} if key in stale else set())
        if amendment:
            allowed.update(amendment['fields'])
            assert macros == amendment['macros'], key
        altered = {field for field in before['task'].keys() | task.keys()
                   if before['task'].get(field) != task.get(field)}
        assert altered <= allowed, (key, altered - allowed)
        assert source_hash(directory, 'gold') == before['recording_hash'], key
        preservation.append({'key': key, 'original_recording_preserved': True,
                             'only_authorized_task_fields_changed': True,
                             'changed_fields': sorted(altered)})
        changes = amendment['changes'] if amendment else []
        limitations = list(previous.get('limitations', []))
        limitations += ['Recorded-evidence replay and targeted counterexamples do not prove universal verifier correctness.',
                        'Semantic and image judges remain probabilistic; full independent-agent reruns were not performed.']
        if key == 'Minh/design-creative_09e218':
            limitations.append('Puppy identity accepts the original fixture and its independently reproduced current Chromium editor JPEG encoding; encoder changes require revalidation.')
        if source == 'gold':
            limitations.append('Original-recording answers can come from task metadata; passing does not independently establish answer correctness.')
        relative = str((out/'tasks'/(key.replace('/', '__')+'.md')).relative_to(ROOT))
        link = 'http://127.0.0.1:8080/annotate/verify?' + urlencode(dict(zip(['annotator','task_id'],key.split('/'))))
        lines = ['# '+key, '', '**AI recommendation: '+recommendation+'** · [Open in annotation interface]('+link+')', '',
                 task['instruction'], '', '## This pass', '']
        if key in stale:
            lines += ['Marked **Stale** at the user’s request for review. Task files and original recordings remain present.']
        lines += ['- '+c for c in changes] or ['No task-specific verifier amendment in this pass; current saved evidence was rerun.']
        lines += ['', '## Open issues', ''] + (['- '+x for x in issues] or ['No unresolved issue identified in this review and its checks.'])
        lines += ['', '## Validation', '', f'Saved positive source: **{source or "none"}**; passed: **{positive}**.', '',
                  '| Probe | Passed | Expected |', '|---|---|---|']
        lines += [f'| {p["name"]} | {p["passed"]} | {p["expected"] if p["expected"] is not None else "diagnostic"} |' for p in row.get('probes', [])]
        lines += [f'| {p["probe"]} | {p["passed"]} | {p["expected"]} |' for p in targeted if p['key'] == key]
        if amendment:
            diff = ''.join(difflib.unified_diff(
                json.dumps(before['verifier']['macros'], indent=2, ensure_ascii=False).splitlines(True),
                json.dumps(macros, indent=2, ensure_ascii=False).splitlines(True), fromfile='before', tofile='after'))
            lines += ['', '## Verifier diff', '', '```diff', diff, '```']
            if amendment['fields']:
                lines += ['', '## Task metadata changes', '', '```json', json.dumps(amendment['fields'], indent=2, ensure_ascii=False), '```']
        lines += ['', '## Limits', ''] + ['- '+x for x in dict.fromkeys(limitations)]
        (ROOT/relative).write_text('\n'.join(lines)+'\n')
        note = ('Deletion suggested; marked Stale for Minh’s review. '+(issues[0] if issues else previous.get('note','')) if key in stale
                else 'Verifier hardening pass: current saved positive evidence passes; empty and answer-only evidence are rejected. '+
                ('The previously documented verifier gaps were repaired and targeted counterexamples checked.' if amendment else 'No new unresolved issue identified.'))
        payloads[key] = {'recommendation': recommendation, 'note': note, 'issues': issues,
                         'changes': list(dict.fromkeys(previous.get('changes', []) + changes)),
                         'limitations': list(dict.fromkeys(limitations)),
                         'documents': list(dict.fromkeys(previous.get('documents', []) + [relative, str((out/'README.md').relative_to(ROOT)), str((out/'stale_review_queue.md').relative_to(ROOT))]))}
        records.append({'key': key, 'recommendation': recommendation, 'review_tag': task.get('review_tag',{}).get('tag'),
                        'source': source, 'positive_passed': positive, 'amended': bool(amendment),
                        'issues': issues, 'changes': changes, 'document': relative,
                        'macros': sorted({canon(m) for m in task.get('macros',[])})})
    probes = [p for row in checks.values() for p in row.get('probes', [])]
    negative_acceptances = sum(p['expected'] is False and p['passed'] for p in probes)
    assert not negative_acceptances
    assert not any(p['unresolved'] for p in probes)
    counts = dict(collections.Counter(r['recommendation'] for r in records))
    coverage = []
    for macro in all_canonical():
        row = {'macro': macro, 'group': entry(macro)['group']}
        for population, valid in [('all', lambda r: True), ('retained', lambda r:r['recommendation']!='suggest_delete'),
                                  ('candidate', lambda r:r['recommendation'] in ('keep','repaired'))]:
            row[population] = sum(macro in r['macros'] and valid(r) for r in records)
            row[population+'_shortfall'] = max(0, 20-row[population])
        coverage.append(row)
    with (out/'macro_coverage.csv').open('w', newline='') as f:
        writer=csv.DictWriter(f, fieldnames=coverage[0].keys());writer.writeheader();writer.writerows(coverage)
    summary = {'tasks':407, 'saved_verifiers':404, 'recommendations':counts,
               'retained_positive_passes':sum(r['positive_passed'] is True and r['recommendation']!='suggest_delete' for r in records),
               'amended_verifiers':len(plan), 'fresh_walks':len(fresh), 'marked_stale':len(stale),
               'automated_probes':len(probes), 'targeted_probes':len(targeted), 'negative_acceptances':negative_acceptances,
               'unit_tests':81, 'registry_checks':4, 'engine_hash':engine_hash(),
               'generated_at':datetime.now(timezone.utc).isoformat(),
               'coverage_unit':'missing task-macro assignments', 'additional_unique_tasks':None,
               'coverage':{name:sum(r[name+'_shortfall'] for r in coverage) for name in ('all','retained','candidate')}}
    write(out/'summary.json', summary);write(out/'reviews.json',records);write(out/'preservation_check.json', preservation)
    write(out/'label_payloads.json',payloads)
    write(out/'candidate_tasks.json',[r['key'] for r in records if r['recommendation'] in ('keep','repaired')])
    with (out/'reviews.csv').open('w', newline='') as f:
        fields=['key','recommendation','review_tag','source','positive_passed','amended','issues','changes','document']
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        writer.writerows({k:' | '.join(r[k]) if isinstance(r[k],list) else r[k] for k in fields} for r in records)
    queue=['# Stale deletion review queue', '', f'**{len(stale)} tasks** marked Stale for Minh to review. Nothing deleted. Previous tags are backed up in [stale_marks.json](stale_marks.json).', '',
           'In the verifier interface, select **Stale** and **AI: Deletion suggested** to isolate this queue.', '',
           '| Task | Reason |', '|---|---|']
    queue += ['| ['+r['key']+'](tasks/'+Path(r['document']).name+') | '+'; '.join(r['issues']).replace('|',' / ')+' |' for r in records if r['key'] in stale]
    (out/'stale_review_queue.md').write_text('\n'.join(queue)+'\n')
    lines=['# Verifier hardening and Stale review queue', '',
           f'**{len(plan)} additional verifiers repaired**, including all eleven previously identified retained-task verifier gaps. **{summary["retained_positive_passes"]} retained tasks** pass current saved-evidence replay. **{len(stale)} deletion candidates are marked Stale** for Minh’s review.', '',
           'The original 35 deletion recommendations were marked Stale, and the task combining event cancellation with unrelated job search was added to that queue. Its executable recording is retained; it needs a coherent task redesign.', '',
           '[Stale review queue](stale_review_queue.md) · [All task records](reviews.csv) · [Candidate task keys](candidate_tasks.json) · [Summary](summary.json) · [Macro coverage](macro_coverage.csv)', '',
           '## Repairs', '', '| Task | Change |','|---|---|']
    lines += ['| ['+r['key']+'](tasks/'+Path(r['document']).name+') | '+' '.join(r['changes']).replace('|',' / ')+' |' for r in records if r['amended']]
    lines += ['', '## Validation and limits', '',
              f'81 regression tests and four macro-registry checks passed. {len(probes)} collection probes completed with no unexpected negative acceptances or unresolved judge calls. All {len(targeted)} targeted positive/negative cases matched their expected results. Five new real browser walkthroughs pass.', '',
              'The targeted checks cover wrong cart contents, intervening cart changes, individual and mixed bulk deletes, extra file/folder deletes, alternative template choice, favorite undo, wrong puppy bytes, missing poster text, later incorrect saves, equivalent wording, wrong exported files, missing export identity, checkout login redirects, incorrect quantities, completed CSV downloads, alternate deletion paths, and wrong clipboard links.', '',
              'Passing saved evidence is not a universal correctness certificate. Counterfactual cases are tests, not successful browser recordings. Most positive checks replay existing walks or original recordings; full independent-agent baselines and reset-variation evaluation remain future work. Semantic and image judges remain probabilistic.', '',
              'PDF and workbook downloads now expose SHA-256 ETags of the actual response bytes; saved-file checks compare decoded bytes to those hashes. Poster checks accept the original puppy fixture and its independently reproduced current editor JPEG encoding.', '',
              'Original recordings and approval decisions are preserved. Task-data changes are limited to authorized Stale tags, two repaired tasks’ semantic/macro metadata, saved verifier specifications, validation evidence and AI review records. All task/spec/tag/label mutations used authenticated annotation APIs. No subagents, deployment, remote upload, or task deletion.', '',
              '## Coverage interpretation', '',
              f'Current gaps: {summary["coverage"]["all"]} counting all tasks; {summary["coverage"]["retained"]} excluding deletion candidates. These are missing task–macro assignments, **not numbers of new tasks**. A feasible grouped creation plan has not been calculated. Five proposed/unassigned macro types remain included.', '',
              '[Targeted probes](targeted_probes.json) · [Fresh walks](fresh_walks.json) · [Preservation checks](preservation_check.json) · [Regression results](regression-tests.txt)']
    (out/'README.md').write_text('\n'.join(lines)+'\n')
    if args.publish:
        import requests
        session=requests.Session()
        for c in read(Path(args.auth_state))['cookies']:
            session.cookies.set(c['name'],c['value'],domain=c['domain'],path=c['path'])
        published=[]
        for key,payload in payloads.items():
            response=session.post('http://127.0.0.1:8080/annotate/api/task_quality/'+key,json=payload,timeout=30)
            assert response.status_code==200,(key,response.status_code)
            published.append(key)
        write(out/'published_labels.json',published)
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
