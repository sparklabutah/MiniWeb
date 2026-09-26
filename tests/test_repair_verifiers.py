"""Regression checks for task repairs: strict values and genuine linked evidence."""
import unittest
from evaluation.verifiers import verify_task, _field_match
from evaluation.trajectory import merge_server_log


def run(node, events, answer=''):
    return verify_task({'macros': {'task': node}}, events, answer)['passed']


def net(url, body=None, response=None, **extra):
    return {'type': 'network', 'method': 'POST', 'url': url, 'status': 200,
            'requestBody': body or {}, 'responseBody': response or {}, **extra}


class RepairVerifierTests(unittest.TestCase):
    def test_strict_fields_and_unicode(self):
        for value in (0, False, 1001, -5):
            self.assertFalse(_field_match({'value': value, 'mode': 'equals'}, None))
            self.assertTrue(_field_match({'value': value, 'mode': 'equals'}, value))
        self.assertFalse(_field_match({'value': -5, 'mode': 'equals'}, 5))
        self.assertFalse(_field_match({'value': 1001, 'mode': 'equals'}, 1002))
        self.assertTrue(_field_match({'value': 'لا يوجد عمل اليوم', 'mode': 'equals'}, 'لا يوجد عمل اليوم'))
        self.assertFalse(_field_match({'value': 'لا يوجد عمل اليوم', 'mode': 'equals'}, 'غداً'))

    def test_order_independent_set_with_no_extras(self):
        wanted = {'value': ['p1', 'p2'], 'mode': 'set_equals'}
        self.assertTrue(_field_match(wanted, ['p2', 'p1']))
        self.assertFalse(_field_match(wanted, ['p1', 'p1']))
        self.assertFalse(_field_match(wanted, ['p1', 'p2', 'p3']))

    def test_numeric_answer_format(self):
        spec = {'type': 'answer_matches', 'expected': '388', 'mode': 'regex', 'pattern': r'388'}
        self.assertTrue(run(spec, [], '388'))
        for answer in ('388 pounds', '388.013581', '389', ''):
            self.assertFalse(run(spec, [], answer))

    def test_creation_binding_and_sequence(self):
        spec = {'type': 'request_sequence', 'steps': [
            {'method': 'POST', 'url': '/create', 'status': 200, 'body_fields': {'title': 'Expenses'},
             'capture': {'id': {'path': 'responseBody.id'}}},
            {'method': 'POST', 'url': 're:/note/{{id}}/save$', 'status': 200, 'body_fields': {'content': 'donation'}},
        ]}
        created = net('/create', {'title': 'Expenses'}, {'id': 731})
        saved = net('/note/731/save', {'content': 'donation'})
        self.assertTrue(run(spec, [created, saved]))
        self.assertFalse(run(spec, [saved, created]))
        self.assertFalse(run(spec, [created, net('/note/732/save', {'content': 'donation'})]))
        self.assertFalse(run(spec, [net('/create', {'title': 'Expenses'}), saved]))
        self.assertFalse(run(spec, []))

    def test_bind_reported_id(self):
        spec = {'type': 'request_sequence', 'steps': [
            {'method': 'POST', 'url': '/order', 'status': 200,
             'capture': {'order': {'path': 'responseBody.order_id'}}}],
            'answer': {'value': '{{order}}', 'mode': 'equals'}}
        events = [net('/order', response={'order_id': 'ORD-521'})]
        self.assertTrue(run(spec, events, 'ORD-521'))
        self.assertFalse(run(spec, events, 'ORD-522'))

    def test_request_count_and_duplicate_logs(self):
        event = net('/book', {'travelers': 2})
        node = {'type': 'request_count', 'match': {'method': 'POST', 'url': '/book', 'status': 200}, 'min': 1, 'max': 1}
        self.assertTrue(run(node, [event, {**event, '_source': 'server_log'}]))
        self.assertFalse(run(node, [event, event]))
        self.assertFalse(run(node, []))

    def test_last_observation_only(self):
        node = {'type': 'observation_matches', 'url': '/saved', 'text': 'No saved translations'}
        empty = {'type': 'observation', 'url': '/saved', 'snapshot': '<p>No saved translations</p>'}
        nonempty = {'type': 'observation', 'url': '/saved', 'snapshot': '<p>Saved translation: bonjour</p>'}
        self.assertTrue(run(node, [nonempty, empty]))
        self.assertFalse(run(node, [empty, nonempty]))
        self.assertFalse(run(node, []))

    def test_response_metadata_survives_merge(self):
        event = {'method': 'POST', 'path': '/create', 'status': 302, 'query': {},
                 'response': {'id': 73}, 'response_headers': {'location': '/note/73'}}
        merged = merge_server_log([], [event])[0]
        self.assertEqual(merged['responseBody'], {'id': 73})
        self.assertEqual(merged['responseHeaders']['location'], '/note/73')


class CatalogRepairTests(unittest.TestCase):
    def test_marketplace_sorts_currency_numerically(self):
        import importlib, sqlite3
        from unittest.mock import patch
        module = importlib.import_module('sites.software-marketplace.routes')
        connection = sqlite3.connect(':memory:')
        connection.row_factory = sqlite3.Row
        connection.execute('CREATE TABLE software_marketplace_apps (id INTEGER, name TEXT, price, category TEXT)')
        connection.executemany('INSERT INTO software_marketplace_apps VALUES (?,?,?,?)',
                               [(1, 'Nine', '$9.99', 'EVENTS'), (2, 'Four hundred', '$400.00', 'EVENTS'),
                                (3, 'Free', 0, 'EVENTS'), (4, 'Malformed', 'Everyone', 'broken')])
        def execute(sql, params=(), fetch='all'):
            cursor = connection.execute(sql, params)
            return cursor.fetchone()[0] if fetch == 'val' else [dict(r) for r in cursor.fetchall()]
        with patch.object(module.db, 'execute', execute):
            apps, total = module._query_apps(category='EVENTS', sort='price_desc')
            self.assertEqual(total, 3)
            self.assertEqual([(a['name'], a['price']) for a in apps], [('Four hundred', 400), ('Nine', 9.99), ('Free', 0)])
            apps, total = module._query_apps(category='EVENTS', sort='price_desc', max_price=10)
            self.assertEqual(total, 2)
            self.assertEqual([a['name'] for a in apps], ['Nine', 'Free'])
        connection.close()

    def test_phone_count_not_capped_by_visible_page(self):
        import importlib, sqlite3
        from unittest.mock import patch
        module = importlib.import_module('sites.comparison-aggregators.routes')
        connection = sqlite3.connect(':memory:');connection.row_factory=sqlite3.Row
        connection.execute('CREATE TABLE comparison_aggregators_phones (id INTEGER, name TEXT, brand TEXT, os TEXT, price TEXT, battery_size TEXT, sim TEXT, released_at TEXT)')
        connection.executemany('INSERT INTO comparison_aggregators_phones VALUES (?,?,?,?,?,?,?,?)',
            [(i, 'Phone '+str(i), 'Acme', 'Android 10', '$90', '4000 mAh', 'Dual SIM', '2020') for i in range(1,106)] +
            [(106,'Expensive','Acme','Android 10','$200','4000 mAh','Dual SIM','2020'),
             (107,'Single','Acme','Android 10','$90','4000 mAh','Single SIM','2020')])
        def execute(sql, params=(), fetch='all'):
            cursor=connection.execute(sql,params)
            return cursor.fetchone()[0] if fetch=='val' else [dict(r) for r in cursor.fetchall()]
        with patch.object(module.db,'get_conn',lambda:connection), patch.object(module.db,'execute',execute):
            rows,total=module._phone_results_page('', '', 'Android', None,100,None,['dual_sim'],'name',1)
            self.assertEqual(total,105);self.assertEqual(len(rows),40)
            last,total=module._phone_results_page('', '', 'Android', None,100,None,['dual_sim'],'name',3)
            self.assertEqual(len(last),25);self.assertEqual(total,105)
        connection.close()

class ReadingProgressTests(unittest.TestCase):
    def test_progress_requires_valid_user_book_and_percentage(self):
        import copy, importlib
        from unittest.mock import patch
        from flask import Flask
        module=importlib.import_module('sites.books-comics.routes')
        app=Flask(__name__);app.secret_key='test';app.register_blueprint(module.blueprint,url_prefix='/books')
        user={'id':1,'name':'Alex','reading_progress':{}}
        writes=[]
        def get_item(site,collection,item_id):
            if collection=='users' and item_id==1:return copy.deepcopy(user)
            if collection=='books' and item_id==61:return {'id':61}
            return None
        with patch.object(module.db,'get_item',get_item),patch.object(module.db,'save_item',lambda *a:writes.append(a)):
            c=app.test_client()
            self.assertEqual(c.post('/books/book/61/progress',json={'progress':40}).status_code,401)
            with c.session_transaction() as s:s['user_id']=1
            self.assertEqual(c.post('/books/book/61/progress',json={'progress':101}).status_code,400)
            self.assertEqual(c.post('/books/book/61/progress',json={'progress':True}).status_code,400)
            self.assertEqual(c.post('/books/book/999/progress',json={'progress':40}).status_code,404)
            response=c.post('/books/book/61/progress',json={'progress':40})
            self.assertEqual(response.json,{'book_id':61,'progress':40,'saved':True})
            self.assertEqual(writes[0][3]['reading_progress'],{'61':40})
            self.assertEqual(len(writes),1)


class AttachmentEvidenceTests(unittest.TestCase):
    def test_file_hash_and_nested_delivery_binding(self):
        spec = {'type': 'request_made', 'method': 'POST', 'url': '/upload', 'status': 200,
                'body_fields': {'_files': {'mode': 'contains_item', 'value': {'filename': 'puppy.jpg', 'sha256': 'correct'}}},
                'response_fields': {'media.file_name': 'puppy.jpg', 'media_has_bytes': {'value': True, 'mode': 'raw_equals'}}}
        good = net('/upload', {'_files': [{'filename': 'puppy.jpg', 'sha256': 'correct'}]},
                   {'media': {'file_name': 'puppy.jpg'}, 'media_has_bytes': True})
        self.assertTrue(run(spec, [good]))
        import copy
        wrong = copy.deepcopy(good); wrong['requestBody']['_files'][0]['sha256'] = 'wrong'
        self.assertFalse(run(spec, [wrong]))
        wrong = copy.deepcopy(good); wrong['responseBody']['media_has_bytes'] = False
        self.assertFalse(run(spec, [wrong]))
        self.assertFalse(run(spec, [net('/upload')]))



class UploadPersistenceTests(unittest.TestCase):
    def test_design_upload_keeps_bytes(self):
        import io, importlib, base64, hashlib
        from unittest.mock import patch
        from flask import Flask
        m=importlib.import_module('sites.design-creative.routes')
        app=Flask(__name__);app.secret_key='test';app.register_blueprint(m.blueprint,url_prefix='/design')
        writes=[];content=b'<svg xmlns="http://www.w3.org/2000/svg"><circle r="1"/></svg>'
        with patch.object(m.db,'next_id',return_value=99),patch.object(m.db,'save_item',side_effect=lambda *a:writes.append(a)),patch.object(m,'emit'):
            c=app.test_client()
            with c.session_transaction() as sess:sess['user_id']=1
            self.assertEqual(c.post('/design/assets/upload',data={'file':(io.BytesIO(content),'profile.jpg')}).status_code,302)
            saved=writes[0][3]
            self.assertEqual(base64.b64decode(saved['src'].split(',')[1]),content)
            self.assertEqual(saved['sha256'],hashlib.sha256(content).hexdigest())
            self.assertEqual(c.post('/design/assets/upload',data={'file':(io.BytesIO(b''),'empty.jpg')}).status_code,400)
            self.assertEqual(len(writes),1)

    def test_chat_welcome_and_file_share_one_message(self):
        import io, importlib, base64
        from unittest.mock import patch
        from flask import Flask
        m=importlib.import_module('sites.team-chat-workspace.routes')
        app=Flask(__name__);app.secret_key='test';app.register_blueprint(m.blueprint,url_prefix='/chat')
        writes=[]
        with patch.object(m,'_current_user',return_value={'id':'tc-u001'}),patch.object(m.db,'get_item',return_value={'id':'ch-general'}),patch.object(m.db,'save_item',side_effect=lambda *a:writes.append(a)),patch.object(m,'_messages',side_effect=AssertionError('must not load collection')):
            c=app.test_client();r=c.post('/chat/api/upload',data={'channel_id':'ch-general','text':'Welcome Mark Roy','file':(io.BytesIO(b'actual resume'),'Resume.pdf')})
            self.assertEqual(r.status_code,302)
            msg=writes[0][3];self.assertEqual(msg['text'],'Welcome Mark Roy')
            self.assertEqual(base64.b64decode(msg['attachment']['data_uri'].split(',')[1]),b'actual resume')
            self.assertEqual(len(writes),1)

    def test_repository_directory_path_and_session_content(self):
        import io, importlib
        from unittest.mock import patch
        from flask import Flask
        m=importlib.import_module('sites.version-control.routes')
        app=Flask(__name__);app.secret_key='test';app.register_blueprint(m.blueprint,url_prefix='/git')
        repo={'id':1004,'name':'test-repo','default_branch':'main'};writes=[]
        with patch.object(m,'_resolve_any_repo',return_value=(repo,False)),patch.object(m,'_session_author',return_value={'username':'alex'}),patch.object(m.db,'next_id',return_value=1),patch.object(m.db,'save_item',side_effect=lambda *a:writes.append(a)):
            r=app.test_client().post('/git/api/repos/1004/upload',data={'path':'src/','commit_message':'Update config','file':(io.BytesIO(b'{"debug":false}'),'config.json')})
            self.assertEqual(r.status_code,201);self.assertEqual(r.json['path'],'src/config.json')
            self.assertEqual(writes[0][3]['content'],'{"debug":false}')
            self.assertNotIn('test-repo',m._FILE_CONTENTS)



class ClipboardBindingTests(unittest.TestCase):
    def test_copy_must_follow_creation_and_name_created_resource(self):
        spec={'type':'request_sequence','steps':[
            {'method':'POST','url':'/create','status':200,'capture':{'id':{'path':'responseBody.id'}}},
            {'type':'action_included','action':'clipboard_write','value':'/sites/campaign/{{id}}'}]}
        created=net('/create',response={'id':73})
        copied={'type':'action','action':'clipboard_write','value':'http://localhost/sites/campaign/73'}
        self.assertTrue(run(spec,[created,copied]))
        self.assertFalse(run(spec,[copied,created]))
        self.assertFalse(run(spec,[created,{**copied,'value':'/campaign/74'}]))
        self.assertFalse(run(spec,[created,{**copied,'value':'http://localhost/sites/campaign/730'}]))
        self.assertFalse(run(spec,[created,{'type':'action','action':'click','target':'Copy link'}]))



class CreationAndDateRepairTests(unittest.TestCase):
    def test_blank_form_values_remain_assertable(self):
        from evaluation.verifiers import _parse_body
        self.assertEqual(_parse_body('title=Test&description=&status=active')['description'],'')
        self.assertFalse(_field_match({'value':'','mode':'raw_equals'},None))

    def test_cloud_launch_returns_created_resource_and_matching_capacity(self):
        import importlib
        from unittest.mock import patch
        from flask import Flask
        m=importlib.import_module('sites.cloud-dev-consoles.routes');app=Flask(__name__);app.secret_key='test'
        app.register_blueprint(m.blueprint,url_prefix='/cloud');writes=[]
        with patch.object(m,'_get_instances',side_effect=AssertionError('no full collection')),patch.object(m.db,'save_item',side_effect=lambda *a:writes.append(a)):
            r=app.test_client().post('/cloud/instances/create',data={'name':'api-prod-3','type':'c5.2xlarge','env':'production','region':'us-west-2'})
            self.assertEqual(r.status_code,302);row=writes[0][3]
            self.assertEqual(row['vcpus'],8);self.assertEqual(row['memory_gb'],16)
            self.assertEqual(r.headers['Location'],'/cloud/instance/'+row['id'])
            self.assertEqual(len(writes),1)

    def test_calendar_creation_owns_and_invites_same_event(self):
        import importlib
        from unittest.mock import patch
        from flask import Flask
        m=importlib.import_module('sites.calendar-todo.routes');app=Flask(__name__);app.secret_key='test'
        app.register_blueprint(m.blueprint,url_prefix='/calendar');writes=[]
        with patch.object(m,'_next_event_id',return_value=731),patch.object(m,'_load_events',side_effect=AssertionError('no full collection')),patch.object(m.db,'save_item',side_effect=lambda *a:writes.append(a)),patch.object(m,'_add_email'):
            r=app.test_client().post('/calendar/create',data={'user_id':'1','title':'Prep','start':'2026-06-16T10:00','end':'2026-06-16T10:30','attendees':'natalie.kim@meridiansystems.com'})
            self.assertEqual(r.status_code,302);row=writes[0][3]
            self.assertEqual(row['user_id'],1);self.assertEqual(row['attendees'],['natalie.kim@meridiansystems.com'])
            self.assertEqual(r.headers['Location'],'/calendar/event/731')


class GridAppendTests(unittest.TestCase):
    def test_append_requires_new_row_and_preserves_existing_cells(self):
        check = {'type': 'form_grid_append', 'initial_url': '/grid',
                 'save': {'method': 'POST', 'url': '/save', 'status': 200},
                 'columns': {'0': '2026-01-04', '1': {'value': 8000, 'mode': 'equals'}}}
        before = {'type': 'observation', 'url': '/grid', 'snapshot':
                  '<input name="cell_0_0" value="2026-03-31"><input name="cell_0_1" value="5000">'}
        cells = {'cell_0_0': '2026-03-31', 'cell_0_1': '5000',
                 'cell_4_0': '2026-01-04', 'cell_4_1': '8000'}
        self.assertTrue(run(check, [before, net('/save', cells)]))
        self.assertFalse(run(check, [net('/save', cells)]))
        self.assertFalse(run(check, [before, net('/save', {**cells, 'cell_0_1': '100'})]))
        self.assertFalse(run(check, [before, net('/save', {**cells, 'rowid_4': 'existing'})]))
        self.assertFalse(run(check, [before, net('/save', {**cells, 'cell_4_1': '7000'})]))


class JobRepairTests(unittest.TestCase):
    def test_full_catalog_salary_ceiling_and_pagination(self):
        import importlib, sqlite3
        from unittest.mock import patch
        m = importlib.import_module('sites.job-sites.routes')
        conn = sqlite3.connect(':memory:'); conn.row_factory = sqlite3.Row
        conn.execute('CREATE TABLE job_sites_jobs(row_id INTEGER PRIMARY KEY, job_title TEXT, company TEXT, salary_range TEXT, job_posting_date TEXT)')
        conn.executemany('INSERT INTO job_sites_jobs VALUES (?,?,?,?,?)',
                         [(i, 'Older job', 'Company', '$61K-$85K', '2023-01-01') for i in range(1, 201)] +
                         [(301, 'Newest eligible', 'Company', '$65K-$82K', '2023-09-15'),
                          (302, 'Boundary', 'Company', '$90K-$100K', '2023-10-01'),
                          (303, 'Range exceeds ceiling', 'Company', '$90K-$130K', '2023-11-01')])
        def execute(sql, params=(), fetch='all'):
            cur = conn.execute(sql, params)
            if fetch == 'val': return cur.fetchone()[0]
            return [dict(r) for r in cur.fetchall()]
        with patch.object(m.db, '_get_conn', return_value=conn), patch.object(m.db, 'execute', side_effect=execute):
            self.assertEqual(m._search_and_filter_jobs(salary_max=99999, limit=1)[0]['row_id'], 301)
            self.assertEqual(m._search_and_filter_jobs(salary_max=99999, count_only=True), 201)
            self.assertEqual(m._search_and_filter_jobs(salary_max=100000, limit=1)[0]['row_id'], 302)
            first = m._search_and_filter_jobs(salary_max=99999, limit=40)
            second = m._search_and_filter_jobs(salary_max=99999, limit=40, offset=40)
            self.assertFalse({r['row_id'] for r in first} & {r['row_id'] for r in second})
        conn.close()

    def test_application_keeps_resume_with_its_own_record(self):
        import io, importlib, base64
        from unittest.mock import patch
        from flask import Flask
        m=importlib.import_module('sites.job-sites.routes')
        app=Flask(__name__);app.secret_key='test';app.register_blueprint(m.blueprint,url_prefix='/jobs')
        user={'id':1,'username':'alex.rivera'}
        job={'job_title':'Data Analyst','company':'Lithia Motors','location':'Abu Dhabi'}
        writes=[]
        with patch.object(m,'_get_browsing_user',return_value=(user,True)),patch.object(m,'_get_job_by_id',return_value=job),patch.object(m.db,'count',return_value=0),patch.object(m.db,'next_id',return_value=900),patch.object(m.db,'save_item',side_effect=lambda *a:writes.append(a)),patch.object(m,'_add_email'),patch.object(m,'render_template',return_value='ok'):
            c=app.test_client();r=c.post('/jobs/apply/616308',data={'cover_letter':'','resume':(io.BytesIO(b'pdf bytes'),'Resume.pdf')})
            self.assertEqual(r.status_code,200)
            saved=writes[0][3]
            self.assertEqual(base64.b64decode(saved['resume_attachment']['data_base64']),b'pdf bytes')
            self.assertFalse(saved['cover_letter_submitted'])
            self.assertEqual(saved['company'],'Lithia Motors')
            self.assertEqual(len(writes),1)


class GridRowSetTests(unittest.TestCase):
    def test_rows_allow_reordering_but_no_missing_extra_or_wrong_fields(self):
        spec={'type':'request_made','method':'POST','url':'/save','status':200,
              'body_grid_rows':[{'0':'Dr. A','1':'Company A'},{'0':'Dr. B','1':'Company B'}],
              'grid_start_row':1,'grid_row_count':2}
        cells={'cell_0_0':'Name','cell_0_1':'Company','cell_1_0':'Dr. B','cell_1_1':'Company B','cell_4_0':'Dr. A','cell_4_1':'Company A'}
        self.assertTrue(run(spec,[net('/save',cells)]))
        self.assertFalse(run(spec,[net('/save',{**cells,'cell_4_1':'Wrong company'})]))
        self.assertFalse(run(spec,[net('/save',{**cells,'cell_5_0':'Unexpected person'})]))
        self.assertFalse(run(spec,[net('/save',{'cell_1_0':'Dr. A','cell_1_1':'Company A'})]))


if __name__ == '__main__':
    unittest.main()


class CheckoutAndPriceRepairTests(unittest.TestCase):
    def test_comma_prices_and_first_advertised_price(self):
        import importlib
        m = importlib.import_module('sites.e-commerce.routes')
        self.assertEqual(m._parse_price('$2,418.74'), 2418.74)
        self.assertEqual(m._parse_price('$22.99$25.99'), 22.99)
        self.assertEqual(m._parse_price(''), 0)

    def test_free_books_create_receipt_without_charging(self):
        import importlib
        from unittest.mock import patch
        from flask import Flask
        m = importlib.import_module('sites.books-comics.routes')
        app = Flask(__name__); app.secret_key = 'test'
        app.register_blueprint(m.blueprint, url_prefix='/books')
        user = {'id':1, 'cart':[19,32], 'reading_list':[19]}
        books = {i:{'id':i,'price':0,'title':str(i)} for i in (19,32)}
        writes=[]
        with patch.object(m,'_get_user',return_value=user), patch.object(m.db,'get_item',side_effect=lambda s,t,i:books[i]), patch.object(m.db,'save_item',side_effect=lambda *a:writes.append(a)), patch.object(m,'_create_order',return_value={'id':731}) as order, patch('app.bank_charges.charge_card') as charge:
            client=app.test_client()
            with client.session_transaction() as session: session['user_id']=1
            response=client.post('/books/checkout',data={'name':'Alex Rivera','email':'alex.rivera@example.com'})
            self.assertEqual(response.status_code,302)
            charge.assert_not_called()
            self.assertEqual(order.call_args.kwargs['payment_method'],'free')
            self.assertEqual(user['cart'],[])
            self.assertEqual(user['reading_list'],[19,32])
            self.assertEqual(len(writes),1)


class MoreEvidenceRepairTests(unittest.TestCase):
    def test_capture_condition_and_response_location(self):
        node={'type':'request_sequence','steps':[{'method':'POST','url':'/trade','status':200,'capture':{'price':{'path':'responseBody.price','matches':{'value':450,'mode':'gt'}}}}]}
        self.assertTrue(run(node,[net('/trade',response={'price':451})]))
        self.assertFalse(run(node,[net('/trade',response={'price':450})]))
        self.assertFalse(run(node,[net('/trade')]))
        header={'type':'request_made','url':'/create','response_headers':{'location':{'value':'/receipt/','mode':'contains'}}}
        self.assertTrue(run(header,[net('/create',responseHeaders={'location':'/receipt/7'})]))
        self.assertFalse(run(header,[net('/create',responseHeaders={'location':'/login'})]))

    def test_uploaded_document_preserves_content_and_bytes(self):
        import io,importlib,base64
        from flask import Flask
        from unittest.mock import patch
        m=importlib.import_module('sites.documents.routes');app=Flask(__name__);app.secret_key='test';app.register_blueprint(m.blueprint,url_prefix='/documents');writes=[]
        with patch.object(m,'_current_user',return_value={'id':1}),patch.object(m.db,'next_id',return_value=731),patch.object(m.db,'save_item',side_effect=lambda *a:writes.append(a)),patch.object(m,'emit'):
            r=app.test_client().post('/documents/upload',data={'file':(io.BytesIO(b'Actual cover letter'),'Cover Letter.docx')})
            self.assertEqual(r.status_code,302);self.assertEqual(writes[0][3]['content'],'Actual cover letter')
            self.assertEqual(base64.b64decode(writes[0][3]['source_attachment']['data_b64']),b'Actual cover letter')


class VisualEvidenceTests(unittest.TestCase):
    def test_eye_requires_saved_bytes_and_judge_acceptance(self):
        import io,base64
        from PIL import Image, ImageDraw
        from unittest.mock import patch
        im=Image.new('RGBA',(120,80));d=ImageDraw.Draw(im);d.ellipse((10,20,110,60),outline='black',width=2);d.ellipse((50,30,70,50),outline='black',width=2)
        b=io.BytesIO();im.save(b,format='PNG');data='data:image/png;base64,'+base64.b64encode(b.getvalue()).decode()
        node={'type':'image_matches','request':{'url':'/save','status':200},'rubric':'eye outline with pupil'}
        with patch('evaluation.evidence_checks._judge_image',return_value=(True,'eye')):
            self.assertTrue(run(node,[net('/save',{'drawing_data':data})]))
            self.assertFalse(run(node,[net('/save',{'drawing_data':''})]))
            self.assertFalse(run(node,[net('/other',{'drawing_data':data})]))
        with patch('evaluation.evidence_checks._judge_image',return_value=(False,'unavailable')):
            self.assertFalse(run(node,[net('/save',{'drawing_data':data})]))

    def test_camera_must_fit_in_circle(self):
        node={'type':'design_matches','request':{'url':'/save','status':200},'rules':[{'kind':'inside_circle','element':{'type':'image','properties.asset_id':6}}]}
        circle={'type':'shape','properties':{'shape':'circle','x':0,'y':0,'width':200,'height':200}}
        camera={'type':'image','properties':{'asset_id':6,'x':60,'y':60,'width':80,'height':80}}
        self.assertTrue(run(node,[net('/save',{'elements':[circle,camera]})]))
        camera['properties']['x']=190
        self.assertFalse(run(node,[net('/save',{'elements':[circle,camera]})]))
        self.assertFalse(run(node,[net('/save',{'elements':[camera]})]))


class PolicyPdfTests(unittest.TestCase):
    def test_pdf_contains_rendered_policy_and_signature_metadata(self):
        import importlib,io
        from pypdf import PdfReader
        m=importlib.import_module('sites.insurance-loans.pdf')
        data=m.policy_pdf('<div class="doc-wrapper"><h2>Renters policy</h2><p>Coverage limit: $100000</p></div>',{'policy_number':'POL-TEST','signed':True,'signed_by':'Alex Rivera','signed_date':'2026-09-01','signed_method':'drawn'})
        self.assertTrue(data.startswith(b'%PDF-'))
        text=' '.join(p.extract_text() for p in PdfReader(io.BytesIO(data)).pages)
        self.assertIn('Coverage limit: $100000',text);self.assertIn('Signed by Alex Rivera',text)

class AddedEvidenceTests(unittest.TestCase):
    def test_recursive_extension_retains_original_and_is_used(self):
        original='print(1)\n'
        spec={'type':'python_extension','original_code':original,'request':{'method':'POST','url':'/execute','status':200}}
        recursion='def f(n):\n    return f(n-1) if n else 0\n'
        self.assertTrue(run(spec,[net('/execute',{'code':original+recursion+'print(f(2))'})]))
        self.assertFalse(run(spec,[net('/execute',{'code':original+recursion})]))
        self.assertFalse(run(spec,[net('/execute',{'code':recursion+'print(f(2))'})]))

    def test_calendar_requires_exact_addition_and_duration(self):
        spec={'type':'calendar_target','url_pattern':r'/calendar\?filtered=1','target':3,'user_id':12,'date_from':'2026-06-22','date_to':'2026-06-28'}
        def view(ids):return {'type':'observation','url':'/calendar?filtered=1','snapshot':''.join(f'<a href="/sites/calendar-todo/event/{i}">event</a>' for i in ids)}
        body={'user_id':12,'category':'work','title':'Meeting','start':'2026-06-24T16:00','end':'2026-06-24T16:30'}
        created=net('/sites/calendar-todo/create',body,status=302)
        self.assertTrue(run(spec,[view([1,2]),created,view([1,2,3])]))
        self.assertFalse(run(spec,[view([1,2]),created,created,view([1,2,3,4])]))
        self.assertFalse(run(spec,[view([1,2]),net('/sites/calendar-todo/create',{**body,'end':'2026-06-24T17:00'},status=302),view([1,2,3])]))

    def test_permit_attachment_is_stored_on_owned_application(self):
        import io, importlib,base64
        from unittest.mock import patch
        from flask import Flask
        m=importlib.import_module('sites.tax-filing-dmv-permits.routes'); app=Flask(__name__);app.secret_key='test';app.register_blueprint(m.blueprint,url_prefix='/gov');writes=[]
        with patch.object(m,'_get_current_user',return_value={'id':1}),patch.object(m.db,'get_item',return_value={'id':8,'user_id':1}),patch.object(m.db,'save_item',side_effect=lambda *a:writes.append(a)):
            r=app.test_client().post('/gov/api/upload',data={'permit_id':'8','file':(io.BytesIO(b'actual image'),'site.png')})
            self.assertEqual(r.status_code,200);self.assertTrue(r.json['attached']);self.assertEqual(writes[0][2],8);self.assertEqual(base64.b64decode(writes[0][3]['attachments'][0]['content_b64']),b'actual image')
        with patch.object(m,'_get_current_user',return_value={'id':2}),patch.object(m.db,'get_item',return_value={'id':8,'user_id':1}),patch.object(m.db,'save_item') as write:
            r=app.test_client().post('/gov/api/upload',data={'permit_id':'8','file':(io.BytesIO(b'image'),'site.png')});self.assertEqual(r.status_code,404);write.assert_not_called()

    def test_shared_editor_snapshot_preserves_edited_code_and_output(self):
        import importlib
        from unittest.mock import patch
        from flask import Flask
        m=importlib.import_module('sites.code-editor-execution.routes');app=Flask(__name__);app.secret_key='test';app.register_blueprint(m.blueprint,url_prefix='/code');writes=[]
        with patch.object(m,'_get_snippet',return_value={'id':19,'title':'Two Sum','code':'original'}),patch.object(m.db,'save_item',side_effect=lambda *a:writes.append(a)):
            r=app.test_client().post('/code/api/share/19',json={'code':'edited program','stdout':'actual output'})
            self.assertEqual(r.status_code,200);self.assertEqual(writes[0][3]['code'],'edited program');self.assertEqual(writes[0][3]['stdout'],'actual output')
        with patch.object(m.db,'get_item',return_value=writes[0][3]):
            r=app.test_client().get(r.json['share_url']);self.assertIn('share=',r.location)

class PlaybackEvidenceTests(unittest.TestCase):
    def test_continuous_playback_needs_elapsed_time_and_rejects_seek(self):
        progress={'method':'POST','url':'/progress','status':200,'body_fields':{'position':{'mode':'between','value':[60,63]}}}
        spec={'type':'playback_span','url':'/episode/24','play_selector':'#play-btn','seek_selectors':['#progress-bar'],'min_seconds':20,'progress_request':progress}
        def action(t,selector='#play-btn'):return {'type':'action','action':'click','selector':selector,'url':'/episode/24','timestamp':f'2026-09-22T00:00:{t:02d}Z'}
        end=net('/progress',{'position':60},timestamp='2026-09-22T00:00:22Z')
        self.assertTrue(run(spec,[action(0),action(21),end]))
        self.assertFalse(run(spec,[action(0),action(5),end]))
        self.assertFalse(run(spec,[action(0),action(10,'#progress-bar'),action(21),end]))

class FinalRepairRegressionTests(unittest.TestCase):
    def test_rental_budget_and_sort_use_monthly_rent(self):
        import sqlite3, importlib
        from unittest.mock import patch
        module=importlib.import_module('sites.real-estate-buy-rent.routes')
        connection=sqlite3.connect(':memory:');connection.row_factory=sqlite3.Row
        connection.execute('CREATE TABLE real_estate_buy_rent_listings (id INTEGER, price REAL, rent_monthly REAL, status TEXT)')
        connection.executemany('INSERT INTO real_estate_buy_rent_listings VALUES (?,?,?,?)',[(1,0,6000,'for_rent'),(2,0,1500,'for_rent'),(3,0,900,'for_rent'),(4,100000,0,'for_sale')])
        def execute(sql,params=(),fetch='all'):
            c=connection.execute(sql,params)
            return c.fetchone()[0] if fetch=='val' else [dict(r) for r in c.fetchall()]
        with patch.object(module.db,'execute',execute):
            rows=module._query_listings(status='for_rent',price_max=5200,sort='price_low')
            self.assertEqual([r['id'] for r in rows],[3,2])
            self.assertEqual(module._query_listings(status='for_rent',price_max=5200,count_only=True),2)
            self.assertEqual([r['id'] for r in module._query_listings(status='for_sale',price_min=90000,sort='price_low')],[4])
        connection.close()

    def test_reported_program_length_matches_successful_code(self):
        spec={'type':'request_sequence','steps':[{'method':'POST','url':'/execute','status':200,'response_fields':{'returncode':{'mode':'equals','value':0}},'capture':{'n':{'path':'requestBody.code','transform':'nonblank_lines'}}}], 'answer':{'mode':'equals','value':'{{n}}'}}
        e=net('/execute',{'code':'\n# comment\nprint(1)\n  \nprint(2)\n'},{'returncode':0})
        self.assertTrue(run(spec,[e],'3'));self.assertFalse(run(spec,[e],'2'))
        self.assertFalse(run(spec,[{**e,'responseBody':{'returncode':1}}],'3'))
        self.assertFalse(run(spec,[net('/execute',response={'returncode':0})],'0'))

    def test_segment_requires_elapsed_time_and_continuous_state(self):
        from datetime import datetime,timedelta
        spec={'type':'playback_span','url':'/rec/4','segment':{'start':420,'end':480},'seek_selectors':['.seek']}
        def stamp(t):return (datetime(2026,9,22)+timedelta(seconds=t)).isoformat()+'Z'
        def view(t,pos,playing,speed=1):return {'type':'observation','url':'/rec/4','timestamp':stamp(t),'snapshot':f'<div data-mini-player data-mp-pos="{pos}" data-mp-playing="{str(playing).lower()}" data-mp-speed="{speed}"></div>'}
        start,end=view(0,420,True),view(60,480,False)
        self.assertTrue(run(spec,[start,end]))
        self.assertFalse(run(spec,[start,view(1,480,False)]))
        self.assertFalse(run(spec,[start,view(30,450,False),end]))
        self.assertFalse(run(spec,[start,view(30,450,True,2),end]))
        self.assertFalse(run(spec,[start,{'type':'action','url':'/rec/4','action':'click','selector':'.seek','timestamp':stamp(30)},end]))
        self.assertFalse(run(spec,[start,view(60,478,False)]))

    def test_published_video_contains_uploaded_bytes(self):
        import io,importlib,base64,hashlib
        from unittest.mock import patch
        from flask import Flask
        m=importlib.import_module('sites.video.routes');app=Flask(__name__);app.secret_key='test';app.register_blueprint(m.blueprint,url_prefix='/video');writes=[];content=b'actual webm bytes'
        with patch.object(m,'_current_user_id',return_value=1),patch.object(m.db,'next_id',return_value=8),patch.object(m.db,'save_item',side_effect=lambda *a:writes.append(a)):
            c=app.test_client();r=c.post('/video/api/videos',data={'title':'Trip','status':'published','file':(io.BytesIO(content),'trip.webm')})
            self.assertEqual(r.status_code,201);stored=writes[0][3];self.assertEqual(base64.b64decode(stored['video_url'].split(',')[1]),content);self.assertEqual(stored['source_attachment']['sha256'],hashlib.sha256(content).hexdigest())
            self.assertEqual(c.post('/video/api/videos',data={'title':'Trip','file':(io.BytesIO(b''),'empty.webm')}).status_code,400)
            self.assertEqual(len(writes),1)

    def test_meeting_attachment_contains_uploaded_bytes(self):
        import io,importlib,base64
        from unittest.mock import patch
        from flask import Flask
        m=importlib.import_module('sites.remote-calls.routes');app=Flask(__name__);app.secret_key='test';app.register_blueprint(m.blueprint,url_prefix='/calls');writes=[]
        with patch.object(m,'_current_user',return_value={'id':'host'}),patch.object(m,'_load_meetings',return_value=[]),patch.object(m.db,'save_collection',side_effect=lambda *a:writes.append(a)),patch('app.bridges.on_booking'):
            r=app.test_client().post('/calls/api/meetings',data={'title':'Review','date':'2026-10-01T10:00','participants':'guest','file':(io.BytesIO(b'agenda bytes'),'notes.txt')})
            self.assertEqual(r.status_code,201);meeting=writes[0][2][0];self.assertEqual(base64.b64decode(meeting['attachment']['content_b64']),b'agenda bytes');self.assertEqual(meeting['participants'],['host','guest'])

    def test_playback_seek_detection_handles_recorder_classes_and_focus(self):
        from evaluation.evidence_checks import PlaybackSpan
        check=PlaybackSpan({'seek_selectors':['button.mp-back','div.mp-seek']})
        event={'type':'action','action':'click','selector':'button.mp-btn.mp-skip.mp-back'}
        self.assertTrue(check._uses_seek_control(event))
        self.assertFalse(check._uses_seek_control({**event,'action':'keypress','value':'Tab'}))
        self.assertTrue(check._uses_seek_control({**event,'action':'keypress','value':'Enter'}))
