import copy,hashlib,unittest
from tools import v2_peer_round as p
class PeerRoundTests(unittest.TestCase):
    def setUp(self):
        self.source=dict(text='甲：请还款。',paragraphs=[dict(id='p1')]);self.review=dict(full_judgment_read=True,source_chars=len(self.source['text']),source_paragraphs=1,source_hash=hashlib.sha256(self.source['text'].encode()).hexdigest())
    def test_matching_review_accepted(self):p.validate_review(self.review,self.source)
    def test_source_mutation_rejected(self):
        self.source['text']='乙：已经还款。'
        with self.assertRaises(AssertionError):p.validate_review(self.review,self.source)
    def test_false_full_read_rejected(self):
        self.review['full_judgment_read']=False
        with self.assertRaises(AssertionError):p.validate_review(self.review,self.source)
    def test_paragraph_count_mismatch_rejected(self):
        self.review['source_paragraphs']=2
        with self.assertRaises(AssertionError):p.validate_review(self.review,self.source)
    def test_answer_revision_can_reuse_same_pixels(self):
        case=dict(language='zh',platform='WeChat',participants=[dict(id='a')],conversations=[],messages=[dict(sender_id='a',text='请还款。')],questions=[dict(answer='旧答案')]);new=copy.deepcopy(case);new['questions'][0]['answer']='修订答案'
        self.assertEqual(p.visible_payload(case),p.visible_payload(new))
        new['messages'][0]['sender_id']='b';self.assertNotEqual(p.visible_payload(case),p.visible_payload(new))
    def test_medium_revision_requires_rerender(self):
        a=dict(platform='WeChat',messages=[]);b=dict(platform='communication_excerpt',source_medium='短信',messages=[])
        self.assertNotEqual(p.visible_payload(a),p.visible_payload(b))
if __name__=='__main__':unittest.main()
