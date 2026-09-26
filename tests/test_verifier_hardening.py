"""Wrong-file, mixed-batch and superseded-state counterexamples."""
import base64
import copy
import hashlib
import unittest
from unittest.mock import patch
from evaluation.verifiers import verify_task, _field_match


def net(url, body=None, response=None, **kw):
    return {'type':'network','method':'POST','url':url,'status':200,
            'requestBody':body or {},'responseBody':response or {},**kw}


def grade(node, events):
    return verify_task({'macros':{'goal':node}}, events, '')['passed']


class VerifierHardeningTests(unittest.TestCase):
    def test_export_digest_checks_actual_bytes(self):
        original=b'%PDF-1.7\ncorrect policy with signature'
        rule={'mode':'base64_sha256','value':hashlib.sha256(original).hexdigest()}
        self.assertTrue(_field_match(rule,base64.b64encode(original).decode()))
        for bad in [b'%PDF-1.7\nunrelated document',original[:-1],b'']:
            self.assertFalse(_field_match(rule,base64.b64encode(bad).decode()))
        self.assertFalse(_field_match(rule,'not base64!'))
        self.assertFalse(_field_match({'mode':'base64_sha256','value':'bad'},'bad'))

    def test_image_filename_cannot_replace_image_identity(self):
        image=b'actual original image'
        rule={'mode':'data_url_sha256','value':hashlib.sha256(image).hexdigest()}
        self.assertTrue(_field_match(rule,'data:image/jpeg;base64,'+base64.b64encode(image).decode()))
        self.assertFalse(_field_match(rule,'data:image/jpeg;base64,'+base64.b64encode(b'other image').decode()))
        self.assertFalse(_field_match(rule,base64.b64encode(image).decode()))

    def test_export_save_binds_current_response(self):
        data=b'workbook';digest=hashlib.sha256(data).hexdigest()
        node={'type':'request_sequence','steps':[
            {'url':'/export','capture':{'digest':{'path':'responseHeaders.etag','regex':'"([a-f0-9]{64})"'}}},
            {'url':'/save','body_fields':{'content_b64':{'mode':'base64_sha256','value':'{{digest}}'}}}]}
        export=net('/export',responseHeaders={'etag':'"'+digest+'"'})
        save=net('/save',{'content_b64':base64.b64encode(data).decode()})
        self.assertTrue(grade(node,[export,save]))
        self.assertFalse(grade(node,[save,export]))
        self.assertFalse(grade(node,[export,net('/save',{'content_b64':base64.b64encode(b'wrong workbook').decode()})]))

    def test_selected_template_is_captured_from_form(self):
        node={'type':'request_sequence','steps':[
            {'url':'/create','capture':{'template':{'path':'requestBody.template_id'}}},
            {'url':'/favorite/{{template}}'}]}
        self.assertTrue(grade(node,[net('/create','template_id=23&title=Photo+studio'),net('/favorite/23')]))
        self.assertFalse(grade(node,[net('/create','template_id=23'),net('/favorite/17')]))

    def test_cart_change_invalidates_earlier_summary(self):
        node={'type':'request_sequence','steps':[
            {'type':'observation_matches','url':'/checkout','text':'Two requested books'},
            {'url':'/checkout','no_intervening':[{'url':'/cart/remove','method':'POST'}]}]}
        view={'type':'observation','url':'/checkout','snapshot':'Two requested books'}
        purchase=net('/checkout');remove=net('/cart/remove')
        self.assertTrue(grade(node,[view,purchase]))
        self.assertFalse(grade(node,[view,remove,purchase]))
        self.assertTrue(grade(node,[view,remove,view,purchase]))
        self.assertTrue(grade(node,[view,{**remove,'status':500},purchase]))

    def test_final_state_guard_works_inside_a_sequence(self):
        node={'type':'request_sequence','steps':[{'url':'/create'},
            {'type':'observation_matches','url':'/favorite/23','text':'Unfavorite',
             'after_requests':[{'url':'/toggle/23','method':'POST'}]}]}
        created=net('/create');view={'type':'observation','url':'/favorite/23','snapshot':'Unfavorite'}
        self.assertTrue(grade(node,[created,view]))
        self.assertFalse(grade(node,[created,view,net('/toggle/23')]))
        self.assertTrue(grade(node,[created,view,net('/toggle/24')]))

    def test_mixed_delete_workflows_require_exact_resource_set(self):
        node={'type':'request_id_set','ids':[1,2,3],'sources':[
            {'request':{'url':'/bulk','status':200},'path':'responseBody.deleted'},
            {'request':{'url':r're:/file/\d+/delete$','status':302},'path':'url','regex':r'/file/(\d+)/delete'}]}
        bulk=net('/bulk',response={'deleted':[1,2]});single=net('/file/3/delete',status=302)
        self.assertTrue(grade(node,[bulk,single]))
        self.assertTrue(grade(node,[net('/file/'+str(i)+'/delete',status=302) for i in (3,2,1)]))
        self.assertFalse(grade(node,[bulk]))
        self.assertFalse(grade(node,[bulk,single,net('/file/4/delete',status=302)]))
        self.assertFalse(grade(node,[bulk,{**single,'status':500}]))
        self.assertFalse(grade(node,[net('/bulk'),single]))

    def test_download_must_complete_before_deletion_witness(self):
        node={'type':'request_sequence','steps':[
            {'url':'/export','status':200},
            {'type':'download_received','url':{'mode':'route','value':'/export'}},
            {'type':'observation_matches','url':'/saved','text':'No saved'}]}
        request=net('/export');download={'type':'download','url':'/export','size':10,'filename':'history.csv'}
        empty={'type':'observation','url':'/saved','snapshot':'No saved'}
        self.assertTrue(grade(node,[request,download,empty]))
        self.assertFalse(grade(node,[request,empty]))
        self.assertFalse(grade(node,[request,empty,download]))

    def test_invisible_required_design_elements_do_not_count(self):
        node={'type':'design_matches','request':{'url':'/save'},
              'rules':[{'kind':'inside_circle','element':{'type':'image'}}]}
        elements=[{'type':'shape','properties':{'shape':'circle','x':0,'y':0,'width':100,'height':100}},
                  {'type':'image','properties':{'x':40,'y':40,'width':20,'height':20}}]
        good=net('/save',{'elements':elements},response={'dimensions':'200x200'})
        self.assertTrue(grade(node,[good]))
        for index in (0,1):
            bad=copy.deepcopy(good);bad['requestBody']['elements'][index]['properties']['opacity']=0
            self.assertFalse(grade(node,[bad]))
        offscreen=copy.deepcopy(good)
        for element in offscreen['requestBody']['elements']:element['properties']['x']-=300
        self.assertFalse(grade(node,[offscreen]))

    def test_direct_design_check_uses_last_save_even_if_fields_differ(self):
        node={'type':'design_matches','request':{'url':'/save','last_for_resource':True,
              'body_fields':{'title':'Logo'}},'rules':[{'kind':'inside_circle','element':{'type':'image'}}]}
        elements=[{'type':'shape','properties':{'shape':'circle','x':0,'y':0,'width':100,'height':100}},
                  {'type':'image','properties':{'x':40,'y':40,'width':20,'height':20}}]
        good=net('/save',{'title':'Logo','elements':elements})
        self.assertTrue(grade(node,[good]))
        self.assertFalse(grade(node,[good,net('/save',{'title':'Other','elements':[]})]))

    def test_only_last_design_save_can_satisfy_geometry_and_text(self):
        node={'type':'request_sequence','steps':[{'url':'/create'},
            {'type':'design_matches','request':{'url':'/save','last_for_resource':True},
             'text':{'mode':'equals','value':'Joe missing. Reward $200.'},
             'rules':[{'kind':'inside_circle','element':{'type':'image'}}]}]}
        elements=[{'type':'shape','properties':{'shape':'circle','x':0,'y':0,'width':100,'height':100}},
                  {'type':'image','properties':{'x':40,'y':40,'width':20,'height':20}},
                  {'type':'text','properties':{'text':'Joe missing. Reward $200.'}}]
        good=net('/save',{'elements':elements});bad=copy.deepcopy(good);bad['requestBody']['elements'][1]['properties']['x']=200
        self.assertTrue(grade(node,[net('/create'),good]))
        self.assertFalse(grade(node,[net('/create'),good,bad]))
        no_text=copy.deepcopy(good);no_text['requestBody']['elements']=elements[:-1]
        self.assertFalse(grade(node,[net('/create'),good,no_text]))
        self.assertTrue(grade(node,[net('/create'),bad,good]))

if __name__=='__main__':unittest.main()
