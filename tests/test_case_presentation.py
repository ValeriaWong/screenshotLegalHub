import copy
import tempfile
import unittest
from pathlib import Path
from legalhub import benchmark as b
from legalhub.casework import CaseWorkspace,HOME
from legalhub.case_presentation import build_presentation,conversation_groups

class CasePresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        work=CaseWorkspace();cls.material=work.material;cls.analysis=work.current;cls.overlay=b.read(HOME/'presentation.json')

    def test_legal_nodes_are_categories_and_do_not_invent_unseen_acts(self):
        graph=build_presentation(self.material,self.analysis,HOME/'presentation.json')
        self.assertEqual(len(graph['legal_events']),8)
        self.assertEqual(len(graph['fact_nodes']),4)
        self.assertTrue(all(e['type'] not in ('withdrawal','revocation','counteroffer') for e in graph['legal_events']))
        self.assertTrue(all(c['status']=='not_seen' for c in graph['legal_checkpoints'] if c['type'] in ('withdrawal','revocation','counteroffer')))
        self.assertTrue(all(e['status']=='undetermined' for e in graph['legal_events'] if e['type'] in ('offer','acceptance')))
        self.assertEqual(graph['model_requests'],0)

    def test_every_new_legal_citation_resolves_to_this_case_verbatim(self):
        graph=build_presentation(self.material,self.analysis,HOME/'presentation.json')
        messages={x['id']:x for x in self.material['records']}
        for e in graph['legal_events']:
            for ref in e['source_refs']:
                self.assertEqual(ref['quote'],messages[ref['message_id']]['text'])
                self.assertIn(e['id'],graph['message_links'][ref['message_id']]['legal_event_ids'])

    def test_contract_evidence_does_not_turn_transfer_into_price_or_fill_delivery(self):
        graph=build_presentation(self.material,self.analysis,HOME/'presentation.json')
        terms={x['key']:x for x in graph['contract_terms']}
        self.assertEqual(terms['price']['status'],'uncertain')
        self.assertEqual(terms['payment']['status'],'statement')
        self.assertEqual(terms['delivery']['status'],'missing');self.assertEqual(terms['delivery']['source_refs'],[])
        self.assertTrue(any(ref['quote']=='[无法辨认]' for ref in terms['price']['source_refs']))

    def test_reviewed_display_group_keeps_original_conversation_ids(self):
        before=copy.deepcopy(self.material);graph=build_presentation(self.material,self.analysis,HOME/'presentation.json')
        self.assertEqual(len(graph['conversations']),1)
        self.assertEqual(len(graph['conversations'][0]['image_ids']),6)
        self.assertEqual(self.material,before)
        self.assertEqual(graph['conversations'][0]['identity_status'],'display_group_only_real_identities_unverified')

    def test_overlay_rejects_foreign_case_and_changed_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'overlay.json';bad=copy.deepcopy(self.overlay);bad['case_id']='another-case';b.write(path,bad)
            with self.assertRaisesRegex(ValueError,'another case'):build_presentation(self.material,self.analysis,path)
            bad=copy.deepcopy(self.overlay);bad['source_hashes'][self.material['images'][0]['image_id']]='changed';b.write(path,bad)
            with self.assertRaisesRegex(ValueError,'images changed'):build_presentation(self.material,self.analysis,path)

    def test_distinct_named_conversations_do_not_share_time_anchors(self):
        images=[{'image_id':'A_image_0.jpg','display_page':1,'conversation_id':'chat-a','conversation_name':'Alice ↔ Bob'},
                {'image_id':'A_image_1.jpg','display_page':2,'conversation_id':'chat-b','conversation_name':'Alice ↔ Carol'}]
        material={'metadata':{'case_id':'A'},'images':images,'records':[
            {'id':'clock','case_id':'A','image_id':images[0]['image_id'],'speaker_local_id':'system','text':'昨天 下午11:30'},
            {'id':'m1','case_id':'A','image_id':images[1]['image_id'],'speaker_local_id':'left','text':'hello'}]}
        graph=build_presentation(material,None)
        self.assertEqual(len(graph['conversations']),2)
        self.assertEqual(graph['message_times']['m1']['basis'],'source_order_only')
        self.assertNotEqual(graph['pages'][0]['conversation_id'],graph['pages'][1]['conversation_id'])

    def test_unknown_conversations_are_not_merged_by_guess(self):
        material=copy.deepcopy(self.material)
        groups,assigned=conversation_groups(material,{})
        self.assertEqual(len(groups),6)
        self.assertEqual(len(set(assigned.values())),6)

if __name__=='__main__':unittest.main()
