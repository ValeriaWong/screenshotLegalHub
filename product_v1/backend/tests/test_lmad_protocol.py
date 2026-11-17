"""L-MAD paper protocol + executed MALLM component checks; zero supplier calls."""
import pytest
from screenshotlegal.method_reproductions.paper_bridge import execute


def request(protocol='hybrid',rounds=3):
    return dict(premise='Daily necessities are excluded from cancellation.',hypothesis='A guardian may cancel daily necessities purchases.',protocol=protocol,rounds=rounds,max_calls=30,scope='scripted_engineering_fixture')

async def test_hybrid_executes_original_components_and_terminates_on_real_unanimity():
    calls=[]
    async def raw(stage,messages,parameters):
        calls.append(dict(stage=stage,messages=messages,parameters=parameters))
        return dict(raw=('Initial independent answer.\nAnswer:N' if stage.startswith('round.1.') else '[AGREE]\nAnswer:N'))
    result=await execute('l_mad',request(),raw)
    assert result['output']['answer']=='N' and result['output']['decision'] is True
    assert len(calls)==5 and len({r['persona'] for r in result['records'][:3]})==3
    assert all(r['visible_message_ids']==[] for r in result['records'][:3])
    assert result['records'][3]['visible_message_ids']==[0,1,2]
    assert result['agreement_checks'][-1]['agreed'] is True
    assert result['LMAD_author_code_executed'] is False and result['upstream_component_code_executed'] is True
    assert all(c['parameters']=={'temperature':.1,'max_tokens':1024} for c in calls)


def test_main_and_appendix_label_parsers_are_separate(monkeypatch):
    from screenshotlegal.method_reproductions.author_bridge import REPO
    monkeypatch.syspath_prepend(str(REPO/'paper/author_reproductions/l_mad'))
    from paper.author_reproductions.l_mad.algorithm import parse_label
    assert parse_label('Answer:N')=='N'
    assert parse_label('判断: N') is None
    assert parse_label('判断: N',appendix=True)=='N'
    assert parse_label('Answer:Y\nAnswer:N') is None


def test_mallm_hybrid_defaults_are_not_lmad_hybrid_configuration(monkeypatch):
    from types import SimpleNamespace
    from screenshotlegal.method_reproductions.author_bridge import REPO
    monkeypatch.syspath_prepend(str(REPO/'paper/author_reproductions/l_mad'))
    from paper.author_reproductions.l_mad.mallm_components import load
    original,_=load();people=[SimpleNamespace(id=str(i)) for i in range(3)]
    old=original.HybridMajorityConsensus(people,0,None)
    lmad=original.ThresholdConsensus(people,0,None,.66,3,None)
    events=[original.Agreement(False,'Answer:N','Answer:N','0','Judge',0),original.Agreement(True,'Agree','','1','Attorney',1)]
    assert old.make_decision(events,3,1,'task','question',None)[1] is False
    assert lmad.make_decision(events,3,1,'task','question',None)[1] is True
    assert old.make_decision.__code__.co_filename.replace(chr(92),'/').endswith('mallm/decision_protocols/consensus.py')


async def test_ranked_tie_runs_exactly_one_supplement_and_keeps_two_round_window():
    calls=[]
    async def raw(stage,messages,parameters):
        calls.append(stage)
        if stage.startswith('vote.3.'):
            return dict(raw={'0':'0 1 2','1':'1 2 0','2':'2 0 1'}[stage.rsplit('.',1)[1]])
        if stage.startswith('vote.4.'):return dict(raw='0 1 2')
        return dict(raw='An independent explanation for '+stage+'\nAnswer:N')
    result=await execute('l_mad',request('ranked'),raw)
    assert result['calls']==18 and result['completed_rounds']==4
    assert [r['agreed'] for r in result['ranking_rounds']]==[False,True]
    assert result['output']['answer']=='N'
    for r in result['records']:
        if r['round']==4:assert r['visible_message_ids']==list(range(3,9))


async def test_unresolved_rank_tie_stays_unknown_instead_of_first_agent_fallback():
    async def raw(stage,messages,parameters):
        if stage.startswith('vote.'):
            return dict(raw={'0':'0 1 2','1':'1 2 0','2':'2 0 1'}[stage.rsplit('.',1)[1]])
        return dict(raw='Answer:N')
    result=await execute('l_mad',request('ranked'),raw)
    assert result['calls']==18 and result['output']['answer'] is None
    assert result['output']['decision'] is False and result['output']['reason']=='rank_tie_after_one_supplement'


async def test_invalid_rank_ballot_has_no_automatic_paid_retry():
    calls=[]
    async def raw(stage,messages,parameters):
        calls.append(stage)
        return dict(raw='0 0 1' if stage.startswith('vote.') else 'Answer:N')
    with pytest.raises(ValueError,match='every candidate exactly once'):
        await execute('l_mad',request('ranked'),raw)
    assert len(calls)==10 and sum(s.startswith('vote.') for s in calls)==1


async def test_per_unit_call_bound_stops_before_next_request():
    calls=[]
    async def raw(stage,messages,parameters):calls.append(stage);return dict(raw='Answer:N')
    payload=request();payload['max_calls']=4
    with pytest.raises(ValueError,match='call bound'):
        await execute('l_mad',payload,raw)
    assert len(calls)==4
