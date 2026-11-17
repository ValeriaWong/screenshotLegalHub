"""Original SOLAR Stage I graph reaches actual human gate without paid calls."""
import json
from screenshotlegal.method_reproductions.author_bridge import REPO,stream_author

async def test_solar_original_stage_i_stops_at_real_human_input(tmp_path):
    tbox=json.loads((REPO/'paper/upstream_sources/solar/eval/sara_tbox_o1.json').read_text(encoding='utf-8'))
    def envelopes(items):return [dict(object=x,confidence=1.,explanation='Protocol fixture from author supplied TBox; not a model result') for x in items]
    calls=[]
    async def handle(event):
        assert event['event']=='request'
        calls.append(event)
        schema=event['original_parameters']['schema']
        if schema=='ConceptExtractionResult':value=dict(classes=envelopes(tbox['classes']),properties=envelopes(tbox['properties']))
        elif schema=='RuleFormulationResult':value=dict(rules=envelopes(tbox['rules']))
        elif schema=='RuleIntegrationResult':value=dict(tbox=tbox)
        else:raise AssertionError('No interpreter generation or Stage II call before human input')
        return dict(raw=json.dumps(value))
    request=dict(statute='Protocol fixture: author supplied TBox outputs only; this is not a statute quality test.',runtime=str(tmp_path))
    result=await stream_author(REPO/'paper/.author_envs/solar/Scripts/python.exe',REPO/'paper/author_reproductions/solar/stage_i_adapter.py',request,handle,python_utf8=True)
    assert result['state']=='awaiting_human_review'
    assert result['checks']['original_human_review_body_executed']
    assert result['checks']['interpreter_generated'] is False
    assert result['checks']['training_evaluated'] is False
    assert result['checks']['product_adaptation_completed'] is False
    assert 'approve' in result['output']['human_review_text']
    assert result['output']['review_state']['human_feedback'] is None
    assert result['output']['tbox']==tbox
    assert 3<=len(calls)<=6
