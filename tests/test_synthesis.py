"""Protect provenance and isolation constraints, without sending model requests."""
import copy
import unittest

from legalhub.synthesis import paragraphs, validate


class SynthesisContractTest(unittest.TestCase):
    def setUp(self):
        self.source = {'paragraphs':[{'id':'p0001','text':'原文聊天：下周还你五百元。'}]}
        self.chat = {
            'facts':[{'id':'f01','source_id':'p0001','source_quote':'下周还你五百元。'}],
            'participants':[{'id':'u1'},{'id':'u2'}],
            'conversations':[{'id':'c1','self_id':'u1','participant_ids':['u1','u2']}],
            'messages':[{'id':'m1','conversation_id':'c1','sender_id':'u1','text':'下周还你五百元。',
                         'origin_type':'verbatim_quote','time_basis':'unknown','timestamp':None,
                         'fact_ids':['f01'],'source_refs':[{'source_id':'p0001','quote':'下周还你五百元。'}]}],
            'events':[{'id':'e1','message_ids':['m1']}],
            'questions':[{'id':'q1','minimal_message_ids':['m1'],'unanswerable':False,'answer_origin':'screenshot_only'}]}

    def test_literal_source_accepts_known_quote(self):
        self.assertTrue(validate(self.chat,self.source)['passed'])

    def test_plausible_but_fabricated_quote_rejected(self):
        chat=copy.deepcopy(self.chat)
        chat['messages'][0]['text']='下周还你五千元。'
        self.assertFalse(validate(chat,self.source)['passed'])

    def test_screenshot_question_cannot_reference_absent_message(self):
        chat=copy.deepcopy(self.chat)
        chat['questions'][0]['minimal_message_ids']=['m99']
        self.assertFalse(validate(chat,self.source)['passed'])

    def test_source_coordinates_reproduce_original_exactly(self):
        text='第一段。\n\n'+'Long evidence '+('a'*2500)+'\n\n最后一段。'
        for p in paragraphs(text):
            self.assertEqual(p['text'],text[p['char_start']:p['char_end']])

    def test_quote_crossing_technical_source_chunks_keeps_literal_integrity(self):
        text='x'*1190+'下周还你五百元，分两次付清。'+'y'*20
        ps=paragraphs(text);source={'text':text,'paragraphs':ps}
        chat=copy.deepcopy(self.chat)
        quote='下周还你五百元，分两次付清。'
        chat['facts'][0].update(source_id='p0001',source_end_id='p0002',source_quote=quote)
        chat['messages'][0].update(text=quote,source_refs=[{'source_id':'p0001','source_end_id':'p0002','quote':quote}])
        self.assertTrue(validate(chat,source)['passed'])
        chat['messages'][0]['source_refs'][0]['quote']='下周还你五千元，分两次付清。'
        self.assertFalse(validate(chat,source)['passed'])


if __name__=='__main__':unittest.main()
