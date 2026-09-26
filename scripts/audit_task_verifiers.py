"""Offline verifier audit. Uses saved evidence; never fabricates successful walks.

Judge-dependent comparisons are marked unresolved in the deterministic pass.
Reports record every task, including exclusions and missing verifiers.
"""
import argparse
import copy
import json
from pathlib import Path
import sys
from contextlib import nullcontext
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from annotation.macros import canon, all_canonical
from annotation.quality import effective_macros
from evaluation.verifiers import verify_task, CHECKS
from evaluation.trajectory import merge_server_log


def nodes(tree, path=()):
    if not isinstance(tree, dict):
        yield path, tree
        return
    yield path, tree
    for field in ('checks', 'steps'):
        for i, child in enumerate(tree.get(field, [])):
            yield from nodes(child, path + (field, i))
    for field in ('request', 'match'):
        if isinstance(tree.get(field), dict):
            yield from nodes(tree[field], path + (field,))


def load_evidence(directory, task):
    walk = directory / 'verification_walk.json'
    # Excluded tasks may have a failed exploratory walk; preserve that distinction.
    runs = directory / 'verifier_runs.json'
    prior = json.loads(runs.read_text()).get('runs', {}) if runs.exists() else {}
    if walk.exists() and prior.get('walk', {}).get('passed'):
        data = json.loads(walk.read_text())
        return data.get('trajectory', []), data.get('answer', ''), 'walk'
    path = directory / 'trajectory.json'
    traj = json.loads(path.read_text()) if path.exists() else []
    traj = merge_server_log(traj, directory / 'server_log.json')
    return traj, task.get('answer') or task.get('expected_answer') or '', 'gold'


def audit_one(key, task, spec):
    row = {'key': key, 'recommendation': task.get('ai_review', {}).get('recommendation', 'unreviewed'),
           'instruction': task.get('instruction', ''), 'findings': [], 'probes': []}
    if not spec or not spec.get('macros'):
        row['findings'].append('No saved verifier')
        return row
    spec = copy.deepcopy(spec)
    spec['macros'] = effective_macros(task, spec['macros'])
    want = {canon(m) for m in task.get('macros', [])}
    if want != set(spec['macros']):
        row['findings'].append('Task and verifier macro keys differ')
    for macro, tree in spec['macros'].items():
        for path, node in nodes(tree):
            if not isinstance(node, dict):
                row['findings'].append('Malformed node: ' + macro + str(path));continue
            if 'op' in node and (not node.get('checks') or node['op'] not in ('AND', 'OR')):
                row['findings'].append('Empty/invalid group: ' + macro + str(path))
            if 'type' in node and node['type'] not in CHECKS:
                row['findings'].append('Unknown check: ' + str(node['type']))
            if any(isinstance(v, dict) and v.get('open') for v in node.values()) and not node.get('advisory'):
                row['findings'].append('Unfilled gating check: ' + macro + str(path))
    traj, answer, source = load_evidence(ROOT / 'data/annotations' / key, task)
    row['source'] = source
    def probe(name, events, output, expected=None):
        report = verify_task(spec, events, output, question=task.get('instruction', ''))
        errors=[]
        def failed(n):
            if n.get('reason') and ('unavailable' in n['reason'].lower() or 'audit: judge' in n['reason'] or 'raised ' in n['reason']):errors.append(n['reason'])
            for child in n.get('checks',[]):failed(child)
        for n in report['macros'].values():failed(n)
        row['probes'].append({'name': name, 'passed': report['passed'], 'expected': expected,
                              'by_macro': report['by_macro'], 'unresolved': errors})
        return report['passed']
    passed=probe('saved_'+source, traj, answer, True)
    probe('empty', [], '', False)
    probe('answer_only', [], answer, False)
    probe('unrelated_activity', [{'type':'action','action':'click','target':'unrelated'}, {'type':'network','method':'GET','url':'/unrelated','status':200}, {'type':'observation','url':'/unrelated','snapshot':'Unrelated page'}], answer, False)
    all_nodes=[n for tree in spec['macros'].values() for _,n in nodes(tree) if isinstance(n,dict)]
    answers=[n for n in all_nodes if (n.get('type') in ('answer_matches','qa_answer') and n.get('leaf', True) is not False)
             or (n.get('type') == 'request_sequence' and 'answer' in n)]
    row['answer_gated']=bool(answers)
    if answers:
        probe('missing_answer',traj,'',False)
        probe('denies_expected_answer',traj,'The answer is not '+str(answer)+'.',False)
        probe('uncertain_answer',traj,'I do not know whether the answer is '+str(answer)+'.',False)
        probe('wrong_answer',traj,'Unrelated answer 987654321',False)
    # Diagnostic ablations require semantic review: outcome-only tasks may
    # legitimately pass without action events or an unnecessary request.
    for kind in ('network','action','observation'):
        probe('without_'+kind,[e for e in traj if e.get('type')!=kind],answer)
    requests=[e for e in traj if e.get('type')=='network' and e.get('method') in ('POST','PUT','PATCH','DELETE')]
    if requests:
        altered=[dict(e,status=500) if e in requests else e for e in traj]
        probe('mutations_return_500',altered,answer)
    from evaluation.verifiers import RequestMade, _parse_body
    # Counterfactual copies are diagnostic probes, never stored as walkthroughs.
    for ni,n in enumerate(all_nodes):
        if n.get('type') != 'request_made' or not n.get('last_for_resource') or '{{' in n.get('url',''):
            continue
        matches=[e for e in traj if RequestMade(n).run([e], '')[0]]
        if not matches:continue
        e=copy.deepcopy(matches[-1]);resp=_parse_body(e.get('responseBody'))
        inverse={'liked':'unliked','saved':'unsaved','starred':'unstarred','followed':'unfollowed',
                 'joined':'left','blocked':'unblocked','subscribed':'unsubscribed','up':'down'}
        changed=False
        for field,w in n.get('response_fields',{}).items():
            if field not in resp:continue
            value=resp[field]
            if isinstance(value,bool):resp[field]=not value;changed=True
            elif isinstance(value,str) and value in inverse:resp[field]=inverse[value];changed=True
        if changed:
            e['responseBody']=resp;e.pop('timestamp',None);e.pop('_source',None)
            probe('undo_final_state_'+str(ni),traj+[e],answer,False)
    if passed:
        probe('harmless_extra_action',traj+[{'type':'action','action':'scroll','target':'page'}],answer,True)
    row['unexpected']=[p['name'] for p in row['probes'] if p['expected'] is not None and p['passed']!=p['expected'] and not p['unresolved']]
    return row


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True);parser.add_argument('--only',default='')
    parser.add_argument('--judge',action='store_true',help='Run configured semantic judge instead of leaving those comparisons unresolved')
    args=parser.parse_args();out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    rows=[]
    with nullcontext() if args.judge else patch('evaluation.verifiers._judge_alignment', return_value=(False,'audit: judge-dependent comparison not executed')):
        for i,path in enumerate(sorted((ROOT/'data/annotations').glob('*/*/task.json')),1):
            key=str(path.parent.relative_to(ROOT/'data/annotations'))
            if args.only and args.only not in key:continue
            task=json.loads(path.read_text());vf=path.parent/'verifier.json';spec=json.loads(vf.read_text()) if vf.exists() else None
            rows.append(audit_one(key,task,spec))
            (out/'automated.json').write_text(json.dumps(rows,indent=2,ensure_ascii=False))
            if i%25==0:print('Audited',i,flush=True)
    print('Complete:',len(rows),'tasks;',sum(len(r.get('probes',[])) for r in rows),'probes;',sum(bool(r.get('unexpected') or r['findings']) for r in rows),'tasks flagged',flush=True)

if __name__=='__main__':main()
