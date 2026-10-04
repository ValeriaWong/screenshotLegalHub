import copy
import unittest
from types import SimpleNamespace
from legalhub.casework import default_material
from legalhub.review_content import build_review_items

class ReviewContentTests(unittest.TestCase):
    def setUp(self):
        self.material=default_material()
        self.row=next(r for r in self.material['records'] if r['text']=='最后一件挺好看')
        self.raw={'key':'quantity','label':'数量','value':'1件','assessment':'模型测试初稿','status':'proposed'}
        self.term={'key':'quantity','label':'数量','value':'购买数量待核','assessment':'展示顺序不等于数量','status':'uncertain','source_refs':copy.deepcopy(self.row['source_refs'])}
        self.graph={'contract_terms':[self.term],'legal_events':[],'conversations':[],'image_conversations':{}}
        self.analysis={'contract_terms':[self.raw],'facts':[],'meanings':[]}
        self.work=SimpleNamespace(material=self.material,state=lambda:{'analysis':self.analysis},timeline=lambda:self.graph)

    def test_preserves_original_and_proposed_text_without_pretending_user_approval(self):
        item=build_review_items(self.work)[0]
        self.assertIn('1件',item['original_text'])
        self.assertIn('购买数量待核',item['proposed_text'])
        self.assertNotIn('review',item)
        self.assertEqual(item['source_refs'][0]['bbox'],self.row['source_refs'][0]['bbox'])
        self.assertEqual(item['source_refs'][0]['quote'],self.row['text'])

    def test_absence_has_context_images_and_no_fabricated_direct_quote(self):
        self.term.update(status='missing',source_refs=[])
        item=build_review_items(self.work)[0]
        self.assertFalse(item['source_coverage']['direct_reference'])
        self.assertEqual(item['source_refs'],[])
        self.assertEqual(len(item['sources']),6)
        self.assertTrue(all(s['context_only'] for s in item['sources']))

    def test_rejects_foreign_reference_and_invented_quote(self):
        self.term['source_refs'][0]['message_id']='foreign'
        with self.assertRaisesRegex(ValueError,'outside'):build_review_items(self.work)
        self.term['source_refs']=copy.deepcopy(self.row['source_refs']);self.term['source_refs'][0]['quote']='模型补造的原话'
        with self.assertRaisesRegex(ValueError,'differs'):build_review_items(self.work)

    def test_fingerprint_stable_on_viewing_changes_on_content_or_original_version(self):
        first=build_review_items(self.work)[0]['source_fingerprint']
        self.assertEqual(first,build_review_items(self.work)[0]['source_fingerprint'])
        self.term['assessment']='修订后的说明'
        self.assertNotEqual(first,build_review_items(self.work)[0]['source_fingerprint'])
        revised=build_review_items(self.work)[0]['source_fingerprint']
        image=next(i for i in self.material['images'] if i['image_id']==self.row['image_id']);image['sha256']='0'*64
        self.assertNotEqual(revised,build_review_items(self.work)[0]['source_fingerprint'])

if __name__=='__main__':unittest.main()
