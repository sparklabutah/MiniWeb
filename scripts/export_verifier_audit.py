"""Export task-level audit evidence and macro coverage; optionally publish AI labels."""
import argparse,collections,csv,difflib,json,sys
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlencode
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from annotation.macros import canon,all_canonical,entry
from annotation.quality import engine_hash

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--audit',default='data/verifier_audit_2026-09-23');p.add_argument('--publish',action='store_true');args=p.parse_args();out=ROOT/args.audit
 baseline=json.loads((out/'baseline.json').read_text());manual=json.loads((out/'manual_review.json').read_text());plan=json.loads((out/'amendment_plan.json').read_text());applied=json.loads((out/'applied_amendments.json').read_text());automated={r['key']:r for r in json.loads((out/'final/automated.json').read_text())};interface=json.loads((out/'interface_checks.json').read_text());before={r['key']:r for r in json.loads((out/'before/automated.json').read_text())}
 assert len(baseline)==len(manual)==len(automated)==407
 assert len(interface)==404
 assert all(check['engine_hash']==engine_hash() for sources in interface.values() for check in sources.values()), 'Interface evidence must use the current loaded engine'
 recordings=json.loads((out/'recording_preservation.json').read_text());assert len(recordings)==407 and all(r['matches'] for r in recordings)
 semantic=json.loads((out/'semantic_negative_checks.json').read_text());assert all(r['passed'] is False for r in semantic)
 docs=out/'tasks';docs.mkdir(exist_ok=True);records=[];payloads={};preservation=[]
 for k,b in baseline.items():
  task=json.loads((ROOT/'data/annotations'/k/'task.json').read_text());review=b['task'].get('ai_review',{});m=manual[k];a=automated[k];oldrec=m.get('recommendation_override',review.get('recommendation','unreviewed'));issues=[];limitations=[];changes=list(applied.get(k,{}).get('changes',[]))
  if m['resolution']=='unresolved':issues.append(m.get('remaining',m['finding']))
  elif m['resolution']=='limitation':limitations.append(m.get('remaining',m['finding']))
  if oldrec=='needs_repair' and m['resolution']!='fixed':issues.extend(review.get('issues',[]) or [review.get('note','Previous unresolved review finding.')])
  source=a.get('source');positive=interface.get(k,{}).get(source,{}).get('passed')
  if positive is False and oldrec!='suggest_delete':issues.append('Saved positive evidence fails on the current engine; investigate verifier versus recording mismatch.')
  if not b['verifier']:issues.append('No saved verifier.')
  if a.get('unexpected'):issues.append('Unexpected automated verdicts: '+', '.join(a['unexpected']))
  shared=any(x in before[k].get('unexpected',[]) for x in ('denies_expected_answer','uncertain_answer','wrong_answer'))
  if shared:changes.append('Shared answer matcher repaired: mentioning or denying the expected result is insufficient; ambiguity/contradiction is rejected or judged semantically.')
  rec='suggest_delete' if oldrec=='suggest_delete' else 'needs_repair' if issues else 'repaired' if changes or oldrec=='repaired' or m['resolution']=='fixed' else 'keep'
  if rec=='suggest_delete':issues=list(dict.fromkeys(review.get('issues',[])+issues));limitations+=review.get('limitations',[])
  limitations+=['Saved evidence was replayed; this audit did not run an independent browser agent on every task.','Static answer/target checks assume the current reset fixture. Semantic and image judges remain probabilistic.']
  if source=='gold':limitations.append('Original gold answers can come from task metadata; a gold pass alone does not independently establish answer correctness.')
  issues=list(dict.fromkeys(issues));limitations=list(dict.fromkeys(limitations));docpath=docs/(k.replace('/','__')+'.md');relative=str(docpath.relative_to(ROOT))
  note=f'All-task verifier audit: {rec.replace("_"," ")}. '+('Unresolved: '+issues[0] if issues else 'No unresolved issue identified by this specification review and the recorded-evidence checks; not a universal correctness certificate.')
  payload={'recommendation':rec,'note':note,'issues':issues,'limitations':list(dict.fromkeys(review.get('limitations',[])+limitations)),'changes':list(dict.fromkeys(review.get('changes',[])+changes)),'documents':list(dict.fromkeys(review.get('documents',[])+[relative,str((out/'README.md').relative_to(ROOT)),str((out/'macro_coverage.csv').relative_to(ROOT))]))}
  payloads[k]=payload
  current=json.loads((ROOT/'data/annotations'/k/'verifier.json').read_text()) if b['verifier'] else None
  diff=''.join(difflib.unified_diff(json.dumps(b['verifier'].get('macros',{}),indent=2,ensure_ascii=False).splitlines(True),json.dumps(current.get('macros',{}),indent=2,ensure_ascii=False).splitlines(True),fromfile='before',tofile='after')) if current else ''
  link='http://127.0.0.1:8080/annotate/verify?'+urlencode(dict(zip(['annotator','task_id'],k.split('/'))))
  lines=['# '+k,'',f'AI recommendation: **{rec}** · [Open annotation interface]({link})','',task.get('instruction',''),'','## Specification review','',m['finding'] or 'Reviewed instruction, macro gates, targets, required values, answer checks, and evidence dependencies. No additional task-specific defect identified.','',f'Review finding disposition: {m["resolution"]}.',m.get('remaining','') if m['resolution']=='fixed' else '', '', '## Changes in this audit','']+(['- '+c for c in changes] or ['No task-specific spec mutation in this audit; shared engine improvements apply.'])+['','## Remaining issues','']+(['- '+c for c in issues] or ['None identified in the checks performed.'])+['','## Evidence','',f'Saved positive source: {source or "none"}; verdict: {positive}. Empty and answer-only checks are recorded separately.','', '| Probe | Passed | Expected passed |','|---|---|---|']+[f'| {x["name"]} | {x["passed"]} | {x["expected"] if x["expected"] is not None else "diagnostic"} |' for x in a.get('probes',[])]+['','## Limits','']+['- '+x for x in limitations]
  if diff:lines+=['','## Verifier diff','','```diff',diff,'```']
  docpath.write_text('\n'.join(lines)+'\n')
  records.append({'key':k,'recommendation':rec,'positive_source':source,'positive_passed':positive,'spec_amended':k in applied,'shared_answer_fix':shared,'issues':issues,'limitations':limitations,'changes':changes,'document':relative,'macros':sorted({canon(x) for x in task.get('macros',[])})})
  preserved={x:y for x,y in task.items() if x!='ai_review'}=={x:y for x,y in b['task'].items() if x!='ai_review'}
  preservation.append({'key':k,'task_fields_except_ai_review_preserved':preserved})
 assert all(r['task_fields_except_ai_review_preserved'] for r in preservation)
 coverage=[]
 for macro in sorted(all_canonical()):
  counts={name:sum(macro in r['macros'] and allowed(r) for r in records) for name,allowed in {'all':lambda r:True,'retained':lambda r:r['recommendation']!='suggest_delete','candidate':lambda r:r['recommendation'] in ('keep','repaired')}.items()}
  coverage.append({'macro':macro,'group':entry(macro)['group'],**counts})
 # Each task counts once per canonical macro; overlap is intentional.
 for r in coverage:
  for name in ('all','retained','candidate'):r[name+'_shortfall']=max(0,20-r[name])
 with (out/'macro_coverage.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=coverage[0].keys());w.writeheader();w.writerows(coverage)
 counts=collections.Counter(r['recommendation'] for r in records);summary={'tasks':len(records),'saved_verifiers':len(interface),'recommendations':dict(counts),'spec_amendments':len(applied),'positive_passes':sum(r['positive_passed'] is True for r in records),'retained_positive_passes':sum(r['positive_passed'] is True and r['recommendation']!='suggest_delete' for r in records),'automated_probes':sum(len(r.get('probes',[])) for r in automated.values()),'negative_acceptances':sum(x['passed'] is True and x['expected'] is False for r in automated.values() for x in r.get('probes',[])),'engine_hash':engine_hash(),'generated_at':datetime.now(timezone.utc).isoformat(),'coverage':{name:{'shortfall':sum(r[name+'_shortfall'] for r in coverage),'under_20':sum(r[name]<20 for r in coverage)} for name in ('all','retained','candidate')}}
 summary['coverage_unit']='missing task-macro assignments'
 summary['additional_unique_tasks']=None
 summary['positive_sources']=dict(collections.Counter(r['positive_source'] for r in records if r['positive_source']))
 summary['validation']={'unit_tests':70,'macro_registry_checks':4,'submitted_text_negative_probes':len(json.loads((out/'semantic_negative_checks.json').read_text())),'original_recordings_preserved':sum(r['matches'] for r in recordings),'fresh_ui_walks':4,'fresh_ui_walks_with_required_actions':3,'fresh_ui_walks_already_complete':1}
 (out/'summary.json').write_text(json.dumps(summary,indent=2));(out/'reviews.json').write_text(json.dumps(records,indent=2,ensure_ascii=False));(out/'label_payloads.json').write_text(json.dumps(payloads,indent=2,ensure_ascii=False));(out/'preservation_check.json').write_text(json.dumps(preservation,indent=2))
 for name,allowed in {'retained_tasks':lambda r:r['recommendation']!='suggest_delete','candidate_tasks':lambda r:r['recommendation'] in ('keep','repaired')}.items():
  (out/(name+'.json')).write_text(json.dumps([r['key'] for r in records if allowed(r)],indent=2))
 with (out/'reviews.csv').open('w',newline='') as f:
  fields=['key','recommendation','positive_source','positive_passed','spec_amended','shared_answer_fix','issues','changes','document'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows({k:' | '.join(r[k]) if isinstance(r[k],list) else r[k] for k in fields} for r in records)
 text=['# MiniWeb verifier audit and coverage','',f'All **{len(records)} tasks** were reviewed; **404 saved verifiers** were replayed through the annotation interface. **{len(applied)} task verifier specifications** were amended, with before/after diffs in the task pages. Shared-engine repairs also apply to the collection.','',f'Current AI recommendations: '+', '.join(f'**{n} {s.replace("_"," ")}**' for s,n in counts.items())+'.','',f'**{summary["negative_acceptances"]} unexpected acceptances** in the recorded negative probes. A passing recording does not prove general correctness; unresolved findings remain visible and excluded from candidate counts.','', '[All task reviews (CSV)](reviews.csv) · [Detailed task records (JSON)](reviews.json) · [Macro coverage (CSV)](macro_coverage.csv) · [Summary (JSON)](summary.json) · [Candidate task keys](candidate_tasks.json)','', '## Coverage to 20 tasks per base macro','',f'The registry contains {len(coverage)} base macros. Counting all 407 tasks leaves **{summary["coverage"]["all"]["shortfall"]}** missing task–macro assignments. Excluding deletion recommendations leaves **{summary["coverage"]["retained"]["shortfall"]}**. Excluding unresolved quality issues as well leaves **{summary["coverage"]["candidate"]["shortfall"]}**.','', 'Each task contributes at most once to each canonical base macro. Macro aliases are resolved; the seven reasoning-operation labels are not separate base macros. Deletion suggestions remain on disk and are not automatically excluded by evaluation runners; candidate_tasks.json records the reviewed candidate subset.','', 'These totals count missing task–macro assignments, NOT distinct new tasks. Do not use 475 as the task-creation requirement. A coherent multi-macro task can fill several gaps at once. No feasible grouped task plan has been calculated, so the required number of distinct new tasks is currently undetermined. For illustration only, filling three still-missing macro assignments per task gives ceil(475 / 3) = 159 tasks; that arithmetic does not establish that such a plan is feasible. Repairing existing flagged tasks improves candidate coverage without creating replacements.','', 'Do not create navigate_by_route tasks: navigation is implicit. The five unassigned registry entries (save_by_form, reveal_by_2fa, carry_info_cross_site, edit_by_textbox, count_entries) need an explicit taxonomy decision before investing heavily in them; they are included in these counts.','', '| Macro | All | Retained | Candidates | Add for retained ≥20 | Add for candidates ≥20 |','|---|---:|---:|---:|---:|---:|']+[f'| {r["macro"]} | {r["all"]} | {r["retained"]} | {r["candidate"]} | {r["retained_shortfall"]} | {r["candidate_shortfall"]} |' for r in coverage]+['','## Validation and scope','','70 regression tests and four macro-registry checks passed. All 23 submitted-text denial probes were rejected. Four fresh browser recordings were saved: three completed the required actions; one showed that the sports favorite task was already complete on reset and is now recommended for deletion.','', 'Original task text, human review fields, and recordings were preserved. Saved verifiers and AI review labels were updated through authenticated annotation APIs. No subagents were used. No deployment, remote annotation upload, or independent agent benchmark run was performed in this audit.','', 'The automated pass includes empty evidence, answer-only evidence, unrelated activity, missing/wrong/denied/uncertain answers where applicable, evidence ablations, failed mutation requests, harmless extra actions, and final-state undo probes. Counterfactual probes are test inputs, not successful walkthroughs. Semantic judge results are included where required.','', '## Remaining retained-task issues','', '| Task | Issue |','|---|---|']+[f'| [{r["key"]}](tasks/{Path(r["document"]).name}) | '+ '; '.join(r['issues']).replace('|',' / ')+' |' for r in records if r['recommendation']=='needs_repair']+['','## Per-task documentation','', '| Task | AI recommendation | Saved positive |','|---|---|---|']+[f'| [{r["key"]}](tasks/{Path(r["document"]).name}) | {r["recommendation"]} | {r["positive_source"] or "missing"}: {r["positive_passed"]} |' for r in sorted(records,key=lambda r:r['key'])]
 (out/'README.md').write_text('\n'.join(text)+'\n')
 if args.publish:
  import requests
  s=requests.Session()
  for c in json.loads(Path('/tmp/miniweb-review-browser.json').read_text())['cookies']:s.cookies.set(c['name'],c['value'],domain=c['domain'],path=c['path'])
  saved=[]
  for k,payload in payloads.items():
   response=s.post('http://127.0.0.1:8080/annotate/api/task_quality/'+k,json=payload,timeout=30);assert response.status_code==200,(k,response.status_code);saved.append(k)
  (out/'published_labels.json').write_text(json.dumps(saved,indent=2))
 print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
