import copy
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from annotation import quality
from scripts.pull_from_railway import _safe_extract, _import_new


class PullTests(unittest.TestCase):
    def test_new_only_preserves_existing_and_records_diff(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); remote = root/'remote'; local = root/'local'
            for base, name, instruction in [(remote,'a','remote'),(local,'a','repaired'),(remote,'b','new')]:
                path = base/'Minh'/name; path.mkdir(parents=True)
                (path/'task.json').write_text(json.dumps({'task_id':name,'instruction':instruction}))
            result = _import_new(remote, local)
            self.assertEqual(result['new'], ['Minh/b'])
            self.assertEqual(result['existing_differences'], [{'key':'Minh/a','files':['task.json']}])
            self.assertEqual(json.loads((local/'Minh/a/task.json').read_text())['instruction'], 'repaired')
            self.assertEqual(_import_new(remote,local)['new'], [])

    def test_unsafe_archives_never_extract(self):
        for name, kind in [('../escape', tarfile.REGTYPE),('/escape',tarfile.REGTYPE),('link',tarfile.SYMTYPE),('hard',tarfile.LNKTYPE)]:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                archive=Path(tmp)/'bad.tar.gz'; dest=Path(tmp)/'dest'; dest.mkdir()
                with tarfile.open(archive,'w:gz') as tar:
                    safe=tarfile.TarInfo('good');safe.size=2;tar.addfile(safe,io.BytesIO(b'ok'))
                    bad=tarfile.TarInfo(name);bad.type=kind;bad.linkname='/tmp/escape';tar.addfile(bad)
                with self.assertRaises(ValueError): _safe_extract(archive,dest)
                self.assertEqual(list(dest.iterdir()), [])


class QualityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.d=Path(self.temp.name)/'Minh'/'task';self.d.mkdir(parents=True)
        self.task={'task_id':'task','annotator':'Minh','instruction':'Do this','macros':['search_by_text'],
                   'review_tag':{'tag':'verified','by':'minh'},'review':{'status':'approved'}}
        self.macros={'search_by_text':{'type':'page_visited','url':'/done'}}
        (self.d/'task.json').write_text(json.dumps(self.task));(self.d/'verifier.json').write_text(json.dumps({'macros':self.macros}))
        (self.d/'trajectory.json').write_text('[]');(self.d/'verification_walk.json').write_text('{"trajectory":[]}')

    def test_ai_review_never_approves_and_invalidates_on_change(self):
        human=copy.deepcopy(self.task['review_tag'])
        quality.save_ai_review(self.d,self.task,{'recommendation':'repaired','note':'Fix'},'codex-review')
        self.assertEqual(quality.summary(self.d,self.task)['ai'],'repaired')
        self.assertEqual(self.task['review_tag'],human);self.assertEqual(self.task['review']['status'],'approved')
        self.task['instruction']='Different task'
        self.assertEqual(quality.summary(self.d,self.task)['ai'],'stale')

    def test_evidence_goes_stale_for_engine_spec_or_recording(self):
        macros=quality.effective_macros(self.task,self.macros)
        quality.record_run(self.d,self.task,macros,'walk',{'passed':True})
        self.assertEqual(quality.summary(self.d,self.task)['walk'],'pass')
        with patch.object(quality,'engine_hash',return_value='changed'):
            self.assertEqual(quality.summary(self.d,self.task)['walk'],'stale')
        (self.d/'verification_walk.json').write_text('{"trajectory":[1]}')
        self.assertEqual(quality.summary(self.d,self.task)['walk'],'stale')

    def test_negative_acceptance_is_a_failure(self):
        macros=quality.effective_macros(self.task,self.macros)
        quality.record_run(self.d,self.task,macros,'empty',{'passed':True})
        row=quality.summary(self.d,self.task)['runs'][0]
        self.assertFalse(row['ok']);self.assertEqual(row['label'],'Accepted')

    def test_running_old_engine_cannot_stamp_new_source_version(self):
        macros=quality.effective_macros(self.task,self.macros)
        quality.record_run(self.d,self.task,macros,'walk',{'passed':True,'engine_hash':'old-loaded-code'})
        row=quality.summary(self.d,self.task)['runs'][0]
        self.assertEqual(row['engine'],'old-loaded-code')
        self.assertTrue(row['stale'])

    def test_api_draft_does_not_record_and_requires_auth(self):
        from flask import Flask
        from annotation.app import annotation_bp
        import annotation.storage as storage
        app=Flask(__name__);app.secret_key='test';app.register_blueprint(annotation_bp,url_prefix='/annotate')
        c=app.test_client();url='/annotate/api/task_quality/Minh/task'
        self.assertEqual(c.get(url).status_code,401)
        with c.session_transaction() as s:s.update(annotator_authenticated=True,annotator_name='codex-review')
        with patch.object(storage,'ANNOTATIONS_DIR',self.d.parent.parent):
            self.assertEqual(c.post(url,json={'recommendation':'invalid'}).status_code,400)
            self.assertEqual(c.post(url,json={'recommendation':'keep'}).status_code,200)
            data={'annotator':'Minh','task_id':'task','which':'empty','macros':{'search_by_text':{'type':'page_visited','url':'/other'}}}
            response=c.post('/annotate/api/run_task_verifier',json=data)
            self.assertEqual(response.status_code,200);self.assertFalse(response.json['evidence_saved'])
            self.assertFalse((self.d/'verifier_runs.json').exists())
            del data['macros'];response=c.post('/annotate/api/run_task_verifier',json=data)
            self.assertTrue(response.json['evidence_saved']);self.assertTrue((self.d/'verifier_runs.json').exists())
            for path in ['.env','data/task_review_x/../../.env','data/task_review_x/../annotations/Minh/task/task.json']:
                self.assertEqual(c.get('/annotate/api/review_document',query_string={'path':path}).status_code,404)

    def test_new_walk_records_who_walked_it_without_staling_evidence(self):
        from flask import Flask
        from annotation.app import annotation_bp
        import annotation.storage as storage
        app=Flask(__name__);app.secret_key='test';app.register_blueprint(annotation_bp,url_prefix='/annotate')
        c=app.test_client()
        with c.session_transaction() as s:s.update(annotator_authenticated=True,annotator_name='claude-review')
        with patch.object(storage,'ANNOTATIONS_DIR',self.d.parent.parent):
            r=c.post('/annotate/api/verification_walk',json={'annotator':'Minh','task_id':'task','trajectory':[]})
        self.assertEqual(r.status_code,200)
        task=json.loads((self.d/'task.json').read_text())
        self.assertEqual(json.loads((self.d/'verification_walk.json').read_text())['recorded_by'],'claude-review')
        by=quality.summary(self.d,task)['walk_by'];self.assertEqual((by['by'],by['ai']),('claude-review',True))
        self.assertEqual(quality.task_hash(task),quality.task_hash(self.task))   # the stamp is not a graded field
        self.assertIsNone(quality.summary(self.d,task)['rerecorded'])
        task.update(rerecorded_at='2026-08-15T21:41:34',rerecorded_by='Minh')
        self.assertEqual(quality.summary(self.d,task)['rerecorded'],{'by':'Minh','at':'2026-08-15T21:41:34'})


class FilteredExportTests(unittest.TestCase):
    def test_csv_uses_inclusive_dates_owner_and_all_pages(self):
        import csv, importlib
        from flask import Flask
        module=importlib.import_module('sites.url-shorteners-qr.routes')
        app=Flask(__name__);app.register_blueprint(module.blueprint,url_prefix='/links')
        def row(i,date):
            return {'id':i,'short_code':str(i),'original_url':'https://example.com','title':'SEO Guide 2025',
                    'owner_id':1,'created_at':date,'clicks':0,'is_active':True}
        first=[row(i,'2025-01-01') for i in range(498)]+[row(498,'2023-12-31'),row(499,'2026-01-02')]
        last=[row(500,'2024-01-01T00:00:00'),row(501,'2026-01-01T23:59:59')]
        with patch.object(module,'_get_current_user',return_value={'id':1}), patch.object(module.db,'query',side_effect=[first,last]) as query:
            result=app.test_client().get('/links/api/export?format=csv&owner_id=999&date_from=2024-01-01&date_to=2026-01-01')
            self.assertEqual(result.status_code,200)
            rows=list(csv.DictReader(io.StringIO(result.text)))
            self.assertEqual(len(rows),500);self.assertEqual({r['owner_id'] for r in rows},{'1'})
            self.assertTrue({'500','501'} <= {r['id'] for r in rows});self.assertFalse({'498','499'} & {r['id'] for r in rows})
            self.assertEqual([c.kwargs['offset'] for c in query.call_args_list],[0,500])
            for call in query.call_args_list:self.assertEqual(call.kwargs['where'],{'owner_id':1});self.assertEqual(call.kwargs['limit'],500)
        with patch.object(module,'_get_current_user',return_value=None):
            self.assertEqual(app.test_client().get('/links/api/export').status_code,401)

if __name__=='__main__':unittest.main()
