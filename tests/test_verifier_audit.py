"""Adversarial regressions found while reviewing the 407-task collection."""
import unittest
from unittest.mock import patch
from evaluation.verifiers import (verify_task, _field_match, _dict_subset,
                                 _match_answer, _cached_alignment, _judge_alignment)


def grade(check, events=(), answer=''):
    return verify_task({'macros': {'task': check}}, list(events), answer)['passed']


def request(url='/item/1/star', response=None, body=None, status=200):
    return {'type': 'network', 'method': 'POST', 'url': url, 'status': status,
            'requestBody': body or {}, 'responseBody': response or {}}


class AuditRegressionTests(unittest.TestCase):
    def test_no_implicit_numeric_tolerance(self):
        for expected, wrong in [(100,101),(1000,1001),(0,.4),(-5,5)]:
            for mode in ('auto','equals','numeric'):
                self.assertFalse(_field_match({'value':expected,'mode':mode},wrong))
        self.assertTrue(_field_match({'value':1000,'mode':'equals'},'1,000.00'))

    def test_literal_text_preserves_meaningful_punctuation(self):
        self.assertFalse(_field_match('project-1','project1'))
        self.assertFalse(_field_match('I agree.','I disagree. I agree.'))
        self.assertTrue(_field_match('Hello world!',' Hello  WORLD! '))

    def test_credentials_are_case_and_punctuation_sensitive(self):
        for rule in ('Abc!42', {'mode':'equals','value':'Abc!42'}):
            self.assertTrue(_dict_subset({'password':rule},{'password':'Abc!42'}))
            for bad in ('abc!42','Abc42',' Abc!42'):
                self.assertFalse(_dict_subset({'password':rule},{'password':bad}))

    def test_missing_no_reward_is_an_explicit_alternative(self):
        self.assertFalse(_field_match({'mode':'equals','value':''},None))
        rule={'mode':'one_of','value':[None,'',0]}
        for v in (None,'',0,'0'):self.assertTrue(_field_match(rule,v))
        self.assertFalse(_field_match(rule,3))

    def test_resource_identity_and_query_order(self):
        node={'type':'request_made','method':'POST','url':'/item/1?a=hello+world&b=2','status':200}
        self.assertTrue(grade(node,[request('/item/1?b=2&a=hello%20world')]))
        self.assertFalse(grade(node,[request('/item/10?a=hello+world&b=2')]))
        self.assertFalse(grade({'type':'page_visited','url':'/item/1'},[{'type':'observation','url':'/item/10'}]))

    def test_follow_action_does_not_match_unfollow(self):
        node={'type':'action_included','action':'click','target':'Follow'}
        self.assertFalse(grade(node,[{'type':'action','action':'click','target':'Unfollow'}]))
        self.assertTrue(grade(node,[{'type':'action','action':'click','target':"button 'Follow'"}]))

    def test_numeric_denials_and_ambiguous_answers(self):
        with patch('evaluation.verifiers._judge_alignment',return_value=(False,'contradiction')):
            for bad in ('The answer is not 1 paper.','There are 2 papers, not 1 paper.',
                        'I do not know whether the answer is 1 paper.','1 or 2 papers'):
                self.assertFalse(_match_answer(bad,'1 paper','contains')[0])
            self.assertTrue(_match_answer('There is 1 paper.','1 paper','contains')[0])
            self.assertFalse(_match_answer('11 hours','11 min','contains')[0])

    def test_names_booleans_arrays_are_not_substring_numbers(self):
        with patch('evaluation.verifiers._judge_alignment',return_value=(False,'different')):
            self.assertFalse(_match_answer('I know','No','contains')[0])
            self.assertFalse(_match_answer('Yes and No','No','contains')[0])
            self.assertFalse(_match_answer('0','[0, 1]','contains')[0])
            self.assertFalse(_match_answer('2026-03-16','2026-03-15','contains')[0])

    def test_reported_relative_url_accepts_origin_but_not_longer_id(self):
        self.assertTrue(_match_answer('Results\nhttp://127.0.0.1:8080/sites/code/s/abc', '/sites/code/s/abc', 'contains')[0])
        self.assertFalse(_match_answer('http://127.0.0.1:8080/sites/code/s/abcd', '/sites/code/s/abc', 'contains')[0])
        self.assertFalse(_match_answer('https://different.example/promo1', 'https://snplnk.io/promo1', 'contains')[0])

    def test_fuzzy_field_does_not_fast_pass_negation(self):
        with patch('evaluation.verifiers._judge_alignment',return_value=(False,'denial')) as judge:
            self.assertFalse(_field_match({'mode':'fuzzy','value':'The project is complete.'},'The project is complete. That statement is false.'))
            judge.assert_called_once()

    def test_empty_invalid_and_missing_reasoning_fail_closed(self):
        for check in ({'op':'AND','checks':[]},{'op':'NOR','checks':[{'type':'page_visited','url':'/'}]},'bad'):
            self.assertFalse(grade(check))
        self.assertFalse(grade({'type':'reasoning_contains','expected':'42'}))

    def test_toggle_cannot_be_undone(self):
        node={'type':'request_made','method':'POST','url':'/item/1/star','status':200,
              'response_fields':{'starred':True},'last_for_resource':True}
        yes=request(response={'starred':True});no=request(response={'starred':False})
        self.assertTrue(grade(node,[yes]))
        self.assertFalse(grade(node,[yes,no]))
        self.assertTrue(grade(node,[yes,request(status=500)]))
        self.assertTrue(grade(node,[no,yes]))

    def test_final_state_scope_distinguishes_resources(self):
        node={'type':'request_made','method':'POST','url':'/star','status':200,
              'body_fields':{'id':1},'identity_fields':['id'],
              'response_fields':{'starred':True},'last_for_resource':True}
        self.assertTrue(grade(node,[request('/star',{'starred':True},{'id':1}),
                                    request('/star',{'starred':False},{'id':2})]))

    def test_sequence_requires_observation_after_last_mutation(self):
        step={'type':'request_made','method':'POST','url':'/toggle','status':200,'last_for_resource':True}
        node={'type':'request_sequence','steps':[step,{'type':'observation_matches','url':'/item','text':'Saved'}]}
        mutate=request('/toggle');view={'type':'observation','url':'/item','snapshot':'Saved'}
        self.assertTrue(grade(node,[mutate,view]))
        self.assertFalse(grade(node,[mutate,view,mutate]))
        self.assertTrue(grade(node,[mutate,view,mutate,view]))

    def test_judge_requires_json_boolean_and_task_context(self):
        _cached_alignment.cache_clear()
        with patch('app.llm.call_llm',return_value='{"match":"false"}') as llm:
            self.assertFalse(_judge_alignment('answer','expected',question='test question')[0])
            self.assertIn('test question',llm.call_args.args[0])
        _cached_alignment.cache_clear()

    def test_mention_insertion_preserves_original_message(self):
        rule={'mode':'text_with_insertion','value':{'original':'Score 94.2%. @aisha please review.', 'insert':'@marc'}}
        for text in ('@marc Score 94.2%. @aisha please review.', 'Score 94.2%. @aisha, @marc please review.', 'Score 94.2%. @aisha please review. @marc'):
            self.assertTrue(_field_match(rule,text))
        self.assertFalse(_field_match(rule,'Score 90%. @aisha, @marc please review.'))
        self.assertFalse(_field_match(rule,'Score 94.2%. @marc please review.'))

    def test_captured_regex_values_are_literal(self):
        node={'type':'request_sequence','steps':[
            {'type':'request_made','url':'/calculate','capture':{'value':{'path':'responseBody.result'}}},
            {'type':'request_made','url':'/save','body_fields':{'result':{'mode':'regex','value':r'{{value}}(?: units)?'}}}]}
        calculated=request('/calculate',{'result':38.45})
        self.assertTrue(grade(node,[calculated,request('/save',body={'result':'38.45 units'})]))
        self.assertFalse(grade(node,[calculated,request('/save',body={'result':'38x45 units'})]))

    def test_last_response_accepts_declared_redirect_status(self):
        node={'type':'request_made','url':'/save','status':[200,302],'last_for_resource':True}
        self.assertTrue(grade(node,[request('/save',status=200),request('/save',status=302)]))
        self.assertFalse(grade(node,[request('/save',status=500)]))

    def test_state_needs_correct_resource_and_no_later_mutation(self):
        node={'type':'observation_matches','url':'/sites/shop/item/1','text':'Saved',
              'after_requests':[{'url':'re:/sites/shop/cart'}]}
        seen={'type':'observation','url':'/sites/shop/item/1','snapshot':'Saved'}
        self.assertTrue(grade(node,[seen]))
        self.assertFalse(grade(node,[{**seen,'url':'/sites/shop/item/10'}]))
        self.assertFalse(grade(node,[seen,request('/sites/shop/cart/remove')]))

    def test_standard_seat_selection(self):
        rule={'mode':'list_of','value':{'count':2,'unique':True,'item':{'mode':'regex','value':r'(?:[5-9]|1[0-5]|1[89]|2[0-9]|30)[A-F]'}}}
        self.assertTrue(_field_match(rule,['5A','22F']))
        for bad in (['1A','5B'],['16A','5B'],['5A','5A'],['5A']):self.assertFalse(_field_match(rule,bad))

    def test_appending_undated_scroll_preserves_server_event_order(self):
        node={'type':'request_sequence','steps':[{'type':'request_made','url':'/save','status':302,'last_for_resource':True},
             {'type':'observation_matches','url':'/sites/demo/item/1','text':'Saved'}]}
        seen={'type':'observation','url':'/sites/demo/item/1','snapshot':'Saved','timestamp':'2026-09-23T00:00:02Z'}
        server={**request('/save',status=302),'timestamp':'2026-09-23T00:00:01Z','_source':'server_log'}
        self.assertTrue(grade(node,[seen,server]))
        self.assertTrue(grade(node,[seen,server,{'type':'action','action':'scroll'}]))

if __name__=='__main__':unittest.main()
