"""Export the reviewed macro plan and publish AI documentation via the interface."""
import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from annotation.macros import all_canonical, group_of
from scripts.review_task_macros import P, read, session


def render():
    baseline, plan = read(P/'baseline.json'), read(P/'plan.json')
    audit = {r['key']: r for r in read(P/'preflight.json')}
    interface = read(P/'interface_checks.json') if (P/'interface_checks.json').exists() else {}
    out = P/'tasks';out.mkdir(exist_ok=True)
    rows, payloads = [], {}
    for key, row in plan.items():
        t = read(ROOT/'data/annotations'/key/'task.json')
        old = baseline[key]['task']
        rec = old['ai_review']['recommendation']
        if rec == 'keep' and row['semantic_changed']:
            rec = 'repaired'
        def tags(task):
            ops = task.get('macro_operations') or {}
            return [m + ('.'+ops[m] if ops.get(m) else '') for m in task.get('macro_instances') or task.get('macros', [])]
        doc = row['task']['macro_ai_review']['document']
        r = audit[key]
        current = interface.get(key, {})
        source = r.get('source')
        passed = current.get(source, {}).get('passed') if current else next((p['passed'] for p in r.get('probes',[]) if p['name'].startswith('saved_')), None)
        status = 'Corrected' if row['semantic_changed'] else 'Checked'
        lines = [f'# {key}', '', f'Macro review: **{status}**. Benchmark recommendation: **{rec}**.', '',
                 t['instruction'], '', '## Tags', '', '| Before | After |', '|---|---|',
                 '| '+ '<br>'.join('`'+m+'`' for m in tags(old))+' | '+'<br>'.join('`'+m+'`' for m in tags(t))+' |', '',
                 '## Review findings', ''] + ['- '+n for n in row['notes']]
        lines += ['', '## Evidence and limits', '',
                  f'- Saved positive source: {source or "none"}; result: {"PASS" if passed else "FAIL" if passed is False else "no saved verifier"}.',
                  '- Empty and answer-only evidence: '+('both rejected' if current and not current.get('empty',{}).get('passed',True) and not current.get('answer_only',{}).get('passed',True) else 'see preflight.json / interface_checks.json')+'.',
                  '- '+row['verifier_note'],
                  f'- {len(t.get("macro_spans",{}))} valid original-recording spans retained. These boundaries were range-checked, not manually re-annotated against repaired walkthroughs.',
                  '- Historical free-text subtask hints not reconfirmed against the revised instruction were removed; the complete originals remain in baseline.json.',
                  '- Instructions, task-level expected answers, recordings, walkthroughs, and human review decisions were not changed by this pass.',
                  '- Semantic/image judges remain probabilistic. Saved replay does not establish coverage of every valid browser workflow.', '',
                  'The full field diff and verifier mapping are in `../plan.json`; previous task/spec data are in `../baseline.json`.', '']
        if rec == 'suggest_delete':
            lines += ['This task remains **Stale for deletion review**. Correcting its tags does not approve its task design.', '']
        (ROOT/doc).write_text('\n'.join(lines))
        ai = old['ai_review']
        payload = {f: ai.get(f, [] if f!='note' else '') for f in ('note','issues','limitations','changes','documents')}
        payload['recommendation'] = rec
        payload['note'] = f'Macro review: {status.lower()}. ' + ai.get('note','')
        payload['changes'] = list(dict.fromkeys(payload['changes'] + row['notes']))
        payload['limitations'] = list(dict.fromkeys(payload['limitations'] + [
            'Macro labels and operations were reviewed; retained action spans are historical gold boundaries, not fresh annotations of repaired walkthroughs.',
            'Repeated macro occurrences are represented separately but saved verifier grading remains per base macro.']))
        payload['documents'] = list(dict.fromkeys(payload['documents'] + [doc, 'data/task_review_macros_2026-09-23/README.md']))
        payloads[key] = payload
        rows.append({'key':key, 'status':status, 'recommendation':rec, 'before':tags(old), 'after':tags(t),
                     'verifier_changed':row['verifier_changed'], 'positive_source':source, 'positive_passed':passed,
                     'notes':row['notes'], 'document':doc})
    summary = {'reviewed':len(rows), 'semantic_corrections':sum(r['status']=='Corrected' for r in rows),
               'no_semantic_correction_needed':sum(r['status']=='Checked' for r in rows),
               'verifier_mappings_updated':sum(r['verifier_changed'] for r in rows),
               'retained':sum(r['recommendation']!='suggest_delete' for r in rows),
               'stale_deletion_candidates':sum(r['recommendation']=='suggest_delete' for r in rows),
               'positive_retained_passes':sum(r['positive_passed'] is True and r['recommendation']!='suggest_delete' for r in rows),
               'preflight_probes':sum(len(r.get('probes',[])) for r in audit.values()),
               'unexpected_negative_acceptances':sum(p['passed'] for r in audit.values() for p in r.get('probes',[]) if p.get('expected') is False),
               'interface_checked':len(interface)}
    all_counts, retained_counts = Counter(), Counter()
    for key,row in plan.items():
        bs=set(row['task']['macros']);all_counts.update(bs)
        if row['task']['ai_review']['recommendation']!='suggest_delete':retained_counts.update(bs)
    with (P/'macro_coverage.csv').open('w') as f:
        writer=csv.writer(f);writer.writerow(['macro','group','all_tasks','retained_tasks','missing_retained_assignments_for_20'])
        for macro in all_canonical():writer.writerow([macro,group_of(macro),all_counts[macro],retained_counts[macro],max(0,20-retained_counts[macro])])
    with (P/'reviews.csv').open('w') as f:
        writer=csv.writer(f);writer.writerow(['task','status','recommendation','before','after','positive_passed','document'])
        for r in rows:writer.writerow([r['key'],r['status'],r['recommendation'],', '.join(r['before']),', '.join(r['after']),r['positive_passed'],r['document']])
    for name,value in [('reviews',rows),('summary',summary),('label_payloads',payloads)]:
        (P/(name+'.json')).write_text(json.dumps(value,indent=2,ensure_ascii=False))
    md=['# Macro tagging review — 407 tasks', '',
        f'**{summary["semantic_corrections"]} tasks corrected; {summary["no_semantic_correction_needed"]} needed no semantic tag correction.** All 407 were reviewed against their current instructions, registry definitions, and saved verifier checks. Ambiguous interaction types were checked against site templates.', '',
        f'{summary["positive_retained_passes"]}/{summary["retained"]} retained tasks pass the reviewed saved evidence. The {summary["stale_deletion_candidates"]} deletion candidates remain Stale; no human review decisions were overwritten.', '',
        f'{summary["preflight_probes"]} preflight probes; {summary["unexpected_negative_acceptances"]} unexpected negative acceptances. {summary["interface_checked"]}/404 saved verifiers replayed through the annotation API.', '',
        'Corrections include missing terminal answers, wrong purchase/reaction/copying labels, unsupported reasoning operations, incidental navigation, and stale graph/instance metadata. The span helper now interprets the UI’s 1-based ranges correctly; terminal QA detection understands repeated instances.', '',
        '**Limits:** historical action boundaries were range-checked but not manually re-annotated against every repaired walkthrough. Repeated instances still share base-macro verifier grading. Semantic and image judges are probabilistic; this is not a fresh independent-agent run on all tasks.', '',
        'Instructions, task-level expected answers, original recordings, repair walkthroughs, and human review fields are preserved. Legacy free-text subtask hints not reconfirmed against revised instructions were removed from active metadata and retained in the complete baseline backup.', '',
        '- [All task reviews (CSV)](reviews.csv)', '- [Machine-readable reviews](reviews.json)',
        '- [Recomputed macro coverage](macro_coverage.csv)', '- [Before/after plan](plan.json)',
        '- [Complete original backup](baseline.json)', '- [Probe results](preflight.json)',
        '- [Interface replay results](interface_checks.json)', '- [Preservation checks](preservation_check.json)', '- [Regression checks](regression-tests.txt)', '- [Browser checks](browser_checks.json)', '',
        'Coverage deficits count **missing task–macro assignments**, not new unique tasks. Proposed macros and legacy navigation need taxonomy decisions before treating all rows as collection targets.', '',
        '| Task | Macro review | Benchmark recommendation |', '|---|---|---|']
    for r in rows:md.append(f'| [{r["key"]}](tasks/{r["key"].replace("/","__")}.md) | {r["status"]} | {r["recommendation"]} |')
    (P/'README.md').write_text('\n'.join(md)+'\n')
    print(summary)


def publish():
    s=session();out=[]
    for key,payload in read(P/'label_payloads.json').items():
        ann,tid=key.split('/')
        r=s.post(f'http://127.0.0.1:8080/annotate/api/task_quality/{ann}/{tid}',json=payload,timeout=30)
        assert r.ok,(key,r.status_code)
        out.append(key)
        (P/'published_labels.json').write_text(json.dumps(out,indent=2,ensure_ascii=False))
        if len(out)%50==0:print('Published review labels',len(out),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--publish',action='store_true');args=parser.parse_args()
    render()
    if args.publish:publish()
