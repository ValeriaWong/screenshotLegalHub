import copy,json
from screenshotlegal.research.leaderboard import leaderboard
from test_leaderboard import store,qa,pipeline,save
from test_leaderboard_categories import benchmark,agent,REACT,REFINE
from test_accounts_ingestion import accounts

def inventory():
    return dict(models=[dict(config_id=k,name=k.title(),model='model-'+k,enabled=True,configured=True) for k in ['alpha','beta']],
        methods=[dict(id='E00',name='One-shot',categories=['oneshot'],available=True),
                 dict(id='E01',name='ReAct',categories=['agent','reproductions'],available=True),
                 dict(id='E05',name='Self-Refine',categories=['reproductions'],available=True),
                 dict(id='E99',name='Planned method',categories=['reproductions'],available=False)])

def test_auto_scope_uses_saved_development_but_never_changes_explicit_official(store):
    pipeline(store,'p1',mode='development_reference')
    result=leaderboard(store,'alice',scope='auto',category='oneshot')
    assert result['scope']=='development' and result['items']
    assert not leaderboard(store,'alice',scope='official',category='oneshot')['items']
    qa(store,'a01')
    assert leaderboard(store,'alice',scope='auto',category='oneshot')['scope']=='official'

def test_registered_models_are_visible_before_any_run_without_scores_or_fake_runs(store):
    board=leaderboard(store,'alice',scope='auto',category='oneshot',inventory=inventory())
    assert not board['cohorts'] and board['total']==2
    assert all(r['catalogue'] and r['rank'] is None and r['score'] is None and r['run_id'] is None for r in board['items'])
    assert {r['model']['config_id'] for r in board['items']}=={'alpha','beta'}

def test_methods_use_selected_base_keep_real_results_and_add_only_missing_candidates(store):
    benchmark(store,'a01',REACT)
    board=leaderboard(store,'alice',scope='auto',category='reproductions',comparison='methods',inventory=inventory(),include_baseline=True)
    assert len([r for r in board['items'] if not r.get('catalogue')])==1
    assert {r['method']['id'] for r in board['items']}=={'E00','E01','E05','E99'}
    assert all(r['model']['config_id']=='alpha' for r in board['items'])
    planned=next(r for r in board['items'] if r['method']['id']=='E99')
    assert planned['status']=='not_implemented' and planned['score'] is None
    other=leaderboard(store,'alice',scope='auto',category='reproductions',comparison='methods',inventory=inventory(),model_id='beta')
    assert not other['cohorts'] and all(r['catalogue'] and r['model']['config_id']=='beta' for r in other['items'])

def test_inventory_search_and_pagination_include_candidates_without_rank(store):
    board=leaderboard(store,'alice',category='oneshot',inventory=inventory(),limit=1)
    assert board['total']==2 and board['next_offset']==1
    second=leaderboard(store,'alice',category='oneshot',inventory=inventory(),offset=1,limit=1)
    assert second['items'][0]['model']['name']!=board['items'][0]['model']['name']
    found=leaderboard(store,'alice',category='oneshot',inventory=inventory(),q='Beta')
    assert len(found['items'])==1 and found['items'][0]['rank'] is None

def test_active_runs_are_visible_only_when_requested_and_cannot_receive_quality_rank(store):
    qa(store,'a01')
    qa(store,'a02',status='running')
    assert len(leaderboard(store,'alice')['items'])==1
    result=leaderboard(store,'alice',include_active=True)
    assert len(result['items'])==2
    active=next(r for r in result['items'] if r.get('active'))
    assert active['score'] is None and active['rank'] is None
    assert next(r for r in result['items'] if not r.get('active'))['score']==1

def test_agent_active_records_still_require_current_case_access(store):
    agent(store,'active',status='running')
    allowed=leaderboard(store,'alice',scope='development',category='agent',include_active=True,case_access=lambda _:True)
    assert allowed['items'][0]['active'] and allowed['items'][0]['score'] is None
    assert not leaderboard(store,'alice',scope='development',category='agent',include_active=True)['items']

def test_method_baseline_delta_is_within_exact_frozen_cohort_only(store):
    benchmark(store,'a01',REACT,score=.75)
    benchmark(store,'a02',dict(id='E00',name='One-shot'),score=.25)
    benchmark(store,'a03',dict(id='E00',name='One-shot'),score=1,release_hash='other')
    b=leaderboard(store,'alice',category='reproductions',comparison='methods',include_baseline=True)
    r=next(r for r in b['items'] if r['method']['id']=='E01')
    assert r['baseline_delta']==.5

def test_catalogue_api_is_opt_in_owner_scoped_read_only_and_credential_free(accounts):
    w,admin,alice,bob=accounts
    alpha=alice.post('/v1/settings/models',json=dict(name='Private Alpha',base_url='https://unit.test/v1',model_name='alpha',
        api_key='synthetic-secret-not-for-response',supports_vision=True,allow_external_egress=True))
    assert alpha.status_code==201,alpha.text
    with alice.app.state.research['store'].read() as db:
        before=[tuple(r) for r in db.execute('select * from records order by kind,id')]
    result=alice.get('/v1/evaluation/leaderboard?scope=auto&category=oneshot&include_catalogue=true').json()
    assert result['items'] and result['items'][0]['catalogue']
    assert 'Private Alpha' in json.dumps(result) and 'synthetic-secret-not-for-response' not in json.dumps(result)
    assert not alice.get('/v1/evaluation/leaderboard?category=oneshot').json()['items']
    other=bob.get('/v1/evaluation/leaderboard?category=oneshot&include_catalogue=true').json()
    assert 'Private Alpha' not in json.dumps(other) and not other['items']
    assert not w.repo.list('egress_audit')
    with alice.app.state.research['store'].read() as db:
        assert [tuple(r) for r in db.execute('select * from records order by kind,id')]==before

def test_kie_roles_and_upstream_score_are_only_attached_to_matching_image_scope(store):
    r,ss,n=pipeline(store,'linked')
    # Same frozen image, separate KIE extraction and enhanced-answer nodes.
    n['variant']='reference_guided_prediction';save(store,'benchmark.pipeline.node',n)
    k=dict(n,id='linked:kie',variant='kie_image',label=None,answer_kind='kie',attempt_id='linked:kie-attempt')
    save(store,'benchmark.pipeline.node',k)
    save(store,'benchmark.attempt',dict(id=k['attempt_id'],run_id=r['id'],pipeline_id=r['id'],task_id='q',status='completed',response={'demo':False}))
    save(store,'benchmark.score',dict(id=k['id']+':'+ss['id'],attempt_id=k['attempt_id'],reference_valid=True,reference_status='human_reviewed',result={'score':.75},scorer_version=ss['scorer_version']))
    row=leaderboard(store,'alice',category='kie_enhanced')['items'][0]
    assert row['pipeline_models']['extractor']['config_id']=='alpha'
    assert row['upstream_kie']==dict(score=.75,eligible=1,scored=1)
    base=leaderboard(store,'alice',category='oneshot')['items'][0]
    assert 'pipeline_models' not in base
