import unittest
from legalhub.case_timeline import build_timeline,visible_clock

class TimelineTests(unittest.TestCase):
    def fixture(self):
        images=[{'image_id':f'A_image_{n}.jpg','display_page':i+1} for i,n in enumerate((0,1,3))]
        records=[{'id':'clock','image_id':images[0]['image_id'],'speaker_local_id':'system','text':'昨天 下午11:30'},
                 {'id':'m1','image_id':images[0]['image_id'],'speaker_local_id':'left','text':'请报价','timestamp_raw':'2099-01-01'},
                 {'id':'m2','image_id':images[1]['image_id'],'speaker_local_id':'right','text':'收到了'},
                 {'id':'m3','image_id':images[2]['image_id'],'speaker_local_id':'left','text':'谢谢'}]
        facts=[{'id':'f1','title':'选购沟通','supporting_message_ids':['m1','m2']}]
        meanings=[{'id':'a1','supporting_message_ids':['m2','m3']},{'id':'a2','supporting_message_ids':['m1','m2']}]
        return {'images':images,'records':records},{'facts':facts,'meanings':meanings}

    def test_real_markers_preserve_unknown_calendar_and_gap_resets_inference(self):
        material,analysis=self.fixture();graph=build_timeline(material,analysis)
        self.assertEqual(graph['pages'][0]['time_label'],'昨天 23:30')
        self.assertEqual(graph['message_times']['m1']['basis'],'after_visible_marker_source_order')
        self.assertIsNone(graph['message_times']['m1']['calendar_date'])
        self.assertEqual(graph['message_times']['m2']['label'],'昨天 23:30之后')
        self.assertEqual(graph['message_times']['m3']['basis'],'source_order_only')
        self.assertFalse(graph['calendar_date_confirmed'])
        self.assertIsNone(visible_clock({'speaker_local_id':'right','text':'12:24'}))

    def test_citation_graph_is_bidirectional_and_keeps_multiple_interpretations(self):
        material,analysis=self.fixture();graph=build_timeline(material,analysis)
        self.assertEqual(graph['message_links']['m2']['meaning_ids'],['a1','a2'])
        self.assertEqual(graph['milestones'][0]['meaning_ids'],['a1','a2'])
        self.assertEqual(graph['meaning_links']['a2']['milestone_ids'],['f1'])
        self.assertEqual(len(graph['milestones'][0]['image_ids']),2)
        self.assertEqual(len(graph['milestones'][0]['source_image_ids']),3)
        self.assertEqual(graph['message_links']['m3']['milestone_ids'],[])
        self.assertEqual(graph['message_links']['m3']['meaning_milestone_ids'],['f1'])
        for record in analysis['meanings']:
            for mid in record['supporting_message_ids']:
                self.assertIn(record['id'],graph['message_links'][mid]['meaning_ids'])
                self.assertIn(mid,graph['meaning_links'][record['id']]['message_ids'])
        self.assertEqual(graph['model_requests'],0)

    def test_timeline_remains_readable_without_analysis_and_rejects_unknown_quotes(self):
        material,analysis=self.fixture();graph=build_timeline(material,None)
        self.assertEqual(len(graph['pages']),3);self.assertEqual(graph['milestones'],[])
        self.assertEqual(graph['message_links']['m2']['meaning_ids'],[])
        analysis['meanings'][0]['supporting_message_ids']=['other-case-message']
        with self.assertRaisesRegex(ValueError,'outside case'):build_timeline(material,analysis)

if __name__=='__main__':unittest.main()
