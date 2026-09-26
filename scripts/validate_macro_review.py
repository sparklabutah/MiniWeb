"""Read-only preservation and structure checks for the applied macro review."""
import json
import sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from annotation.macros import all_canonical,operation_names
from annotation.quality import source_hash,summary,engine_hash
from scripts.review_task_macros import P,read,base

def main():
    baseline,plan=read(P/'baseline.json'),read(P/'plan.json')
    checks=read(P/'interface_checks.json');failures=[];counts=Counter()
    preserved=('instruction','instruction_revision','expected_answer','answer','answer_type','alternatives',
               'starting_url','sites','review','review_tag','task_audit','annotator','saved_at')
    def check(ok,key,detail):
        if not ok:failures.append({'key':key,'detail':detail})
    for key,b in baseline.items():
        d=ROOT/'data/annotations'/key;t=read(d/'task.json');old=b['task'];r=plan[key]
        for f in preserved:check(t.get(f)==old.get(f),key,'Preservation: '+f)
        check(source_hash(d,'gold')==b['recording_hash'],key,'Original recording changed')
        check(source_hash(d,'walk')==b['walk_hash'],key,'Repair walk changed')
        for f,want in r['fields'].items():check(t.get(f)==want,key,'Plan mismatch: '+f)
        ns=t['macro_instances'];check(len(ns)==len(set(ns)),key,'Duplicate instance ID')
        check(t['macros']==list(map(base,ns)),key,'Base/instance mismatch')
        check(all(base(n) in all_canonical() for n in ns),key,'Unknown macro')
        check(t['num_macros']==len(ns),key,'Wrong macro count')
        for f in ('macro_operations','macro_spans','macro_positions','macro_subtasks','qa_answers'):
            check(set(t[f])<=set(ns),key,'Dangling '+f)
        check(all(op in operation_names() for op in t['macro_operations'].values()),key,'Unknown operation')
        check([a['instance'] for a in t['macro_tags']]==ns,key,'Tag/instance mismatch')
        graph={n:[] for n in ns}
        for e in t['macro_edges']:
            check(e['from'] in ns and e['to'] in ns,key,'Dangling edge')
            check(e['from']!='report_information',key,'Nonterminal final report')
            graph[e['from']].append(e['to'])
        def cycle(n,stack):
            return n in stack or any(cycle(c,stack|{n}) for c in graph[n])
        check(not any(cycle(n,set()) for n in ns),key,'Graph cycle')
        q=summary(d,t);check(q['ai']!='stale',key,'AI review outdated')
        counts[q['recommendation']]+=1
        if old['ai_review']['recommendation']=='suggest_delete':
            check(t.get('review_tag',{}).get('tag')=='stale',key,'Deletion candidate lost Stale label')
        if b['verifier']:
            check(read(d/'verifier.json')['macros']==r['macros'],key,'Saved verifier differs from plan')
            check(key in checks,key,'Missing API replay')
            for source,result in checks.get(key,{}).items():
                check(result['engine_hash']==engine_hash(),key,'Replay used old engine')
                if source in ('empty','answer_only'):check(result['passed'] is False,key,'Negative evidence accepted')
                elif old['ai_review']['recommendation']!='suggest_delete':
                    check(result['passed'] is True,key,'Retained positive failed')
                check(any(run['source']==source and not run['stale'] for run in q['runs']),key,'Saved replay evidence outdated')
    result={'tasks_checked':len(plan),'saved_verifiers_checked':len(checks),'preserved_fields':list(preserved),
            'recordings_and_walks_preserved':not any('recording' in f['detail'].lower() or 'walk changed' in f['detail'].lower() for f in failures),
            'recommendations':dict(counts),'engine_hash':engine_hash(),'failures':failures}
    (P/'preservation_check.json').write_text(json.dumps(result,indent=2,ensure_ascii=False));print(json.dumps(result,indent=2))
    assert not failures
if __name__=='__main__':main()
