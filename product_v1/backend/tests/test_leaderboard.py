import copy
import json
import pytest
from screenshotlegal.research.store import Store
from screenshotlegal.research.leaderboard import leaderboard
from test_accounts_ingestion import accounts
from test_research_products import lab

@pytest.fixture
def store(tmp_path):
    value=Store(tmp_path)
    yield value
    value.close()

def save(store,kind,row,owner="alice"):
    with store.tx() as db:store.put(kind,row,owner,db)

def qa(store,id,config="alpha",scores=(1,1),statuses=None,owner="alice",**changes):
    model=dict(id=id+":model",config_id=config,name=config.title(),model="model-"+config,endpoint="https://unit.test/v1",
               parameters={"temperature":0},timeout_policy={"read":90},credential_ref="SECRET_SENTINEL")
    tasks=[dict(id=id+":"+str(i),sample_id="sample",revision=1,question_id="q"+str(i),input_hash="input"+str(i),gold_answer="PRIVATE_GOLD",model=model,category="chat",task_type="qa",input={"question":"Synthetic question","mode":"text"}) for i in range(len(scores))]
    run=dict(id=id,name=id,status="completed",created_at="2026-10-29T00:00:"+id[-2:]+ "+00:00",binding_contract="research.v2",release_id="release",release_hash="frozen-release",
             mode="text",tasks=tasks,max_calls=100,parent_run_id=None,frozen_sample_ids=["sample"],concurrency=1)
    run.update(changes);save(store,"evaluation.run",run,owner)
    for i,score in enumerate(scores):
        status=statuses[i] if statuses else "completed"
        save(store,"evaluation.attempt",dict(id=id+":a"+str(i),run_id=id,task_id=tasks[i]["id"],status=status,score=score,scoring_status="exact_match",answer="synthetic answer",
             latency_ms=100+i,cost=.001,cost_currency="CNY",response={"raw":"PRIVATE_RESPONSE","demo":False},
             error={"category":"network"} if status=="failed" else None),owner)
    return run

def test_rank_uses_latest_not_best_and_failed_gold_remains_in_denominator(store):
    qa(store,"a01",scores=(1,1))
    qa(store,"a02",scores=(1,None),statuses=("completed","failed"))
    qa(store,"b03","beta",scores=(1,1))
    qa(store,"c04","gamma",scores=(1,1))
    result=leaderboard(store,"alice")
    assert len(result["cohorts"])==1
    rows=result["items"]
    assert [r["model"]["name"] for r in rows]==["Beta","Gamma","Alpha"]
    assert [r["rank"] for r in rows]==[1,1,3]
    last=rows[-1]
    assert last["run_id"]=="a02" and last["repeated_runs"]==2
    assert last["score"]==.5 and last["conditional_score"]==1 and last["score_coverage"]==.5
    assert last["failed"]==1 and last["eligible"]==2

def test_snapshot_scope_mode_parameters_and_reference_changes_split_cohorts(store):
    qa(store,"a01")
    qa(store,"b02","beta",release_hash="different-release")
    qa(store,"c03","gamma",mode="image")
    qa(store,"d04","delta",max_calls=20)
    assert len(leaderboard(store,"alice")["cohorts"])==4

def test_demo_retries_active_unbound_and_other_owner_are_not_promoted(store):
    qa(store,"a01")
    qa(store,"b02","demo")
    qa(store,"c03","retry",parent_run_id="a01")
    qa(store,"d04","active",status="running")
    qa(store,"e05","legacy",binding_contract="old")
    qa(store,"f06","hidden",owner="bob")
    result=leaderboard(store,"alice")
    assert len(result["items"])==1
    counts={r["reason"]:r["count"] for r in result["summary"]["excluded"]}
    assert all(counts[k]==1 for k in ["demo","retry","active","legacy"])
    assert "Hidden" not in json.dumps(result)
    other=leaderboard(store,"bob")
    with pytest.raises(KeyError):leaderboard(store,"alice",cohort_id=other["selected_cohort_id"]+"missing")

def test_pending_scoring_is_unranked_and_missing_costs_and_latency_are_not_zero(store):
    run=qa(store,"a01",scores=(None,None))
    with store.tx() as db:
        for a in store.list("evaluation.attempt","alice",db):
            a.update(cost=None,latency_ms=None);store.put("evaluation.attempt",a,"alice",db)
    row=leaderboard(store,"alice")["items"][0]
    assert row["score"] is None and row["rank"] is None
    assert row["pending_scoring"]==2 and row["unranked_reason"]
    assert row["cost"] is None and not row["cost_complete"] and row["latency_p50_ms"] is None

def test_search_pagination_and_sort_preserve_quality_ranks_and_are_read_only(store):
    qa(store,"a01",scores=(0,0))
    qa(store,"b02","beta",scores=(1,1))
    with store.read() as db:before=[tuple(r) for r in db.execute("SELECT * FROM records ORDER BY kind,id")]
    r=leaderboard(store,"alice",q="Alpha",sort="latency",limit=1)
    assert r["items"][0]["rank"]==2
    assert leaderboard(store,"alice",limit=1)["next_offset"]==1
    assert leaderboard(store,"alice",limit=1,offset=1)["items"][0]["rank"]==2
    assert "SECRET_SENTINEL" not in json.dumps(r) and "PRIVATE_GOLD" not in json.dumps(r) and "PRIVATE_RESPONSE" not in json.dumps(r)
    with store.read() as db:assert [tuple(r) for r in db.execute("SELECT * FROM records ORDER BY kind,id")]==before

def test_mixed_currency_is_not_added_as_one_total(store):
    qa(store,"a01")
    with store.tx() as db:
        a=store.list("evaluation.attempt","alice",db)[0];a["cost_currency"]="USD";store.put("evaluation.attempt",a,"alice",db)
    row=leaderboard(store,"alice")["items"][0]
    assert row["cost"] is None and not row["cost_complete"]

def pipeline(store,id,model="alpha",mode="official_reviewed",score=1):
    task=dict(task_id="q",source_task_hash="task-hash",asset={"sha256":"image"},question="Visible question",roi=None,
              output_schema={"answer":"string"},target="private-gold",answer_kind="text",reference_valid=True,reference_status="human_reviewed")
    bundle=dict(id=id+":bundle",tasks=[task])
    n=dict(id=id+":node",pipeline_id=id,task_id="q",task_bundle_id=bundle["id"],variant="full_image",answer_kind="text",
           label="content",status="response_received",attempt_id=id+":attempt")
    model=dict(id=id+":model",config_id=model,name=model.title(),model="model-"+model,endpoint="https://unit.test/v1",parameters={"temperature":0})
    ss=dict(id=id+":ss",pipeline_id=id,scorer_version="kie-vqa-score.v1",overrides={})
    run=dict(id=id,name=id,created_at="2026-10-29T00:00:01+00:00",status="completed",mode=mode,dataset_id="dataset",
             release_hash="release" if mode=="official_reviewed" else None,score_set_id=ss["id"],model=model,
             prompts={"vqa":{"sha256":"prompt"}},protocol="A.v1",variants={"full_image":1},max_calls=10)
    for kind,row in [("benchmark.pipeline",run),("benchmark.pipeline.node",n),("benchmark.pipeline.task",bundle),("benchmark.scoreset",ss),
                     ("benchmark.attempt",dict(id=n["attempt_id"],pipeline_id=id,run_id=id,task_id="q",status="completed",response={"demo":False})),
                     ("benchmark.score",dict(id=n["id"]+":"+ss["id"],pipeline_id=id,attempt_id=n["attempt_id"],reference_valid=True,reference_status="human_reviewed",target="private-gold",scorer_version=ss["scorer_version"],result={"score":score,"status":"scored"}))]:
        save(store,kind,row)
    return run,ss,n

def test_pipeline_ignores_run_specific_ids_and_uses_only_current_score_set(store):
    pipeline(store,"p1")
    p,ss,n=pipeline(store,"p2","beta",score=0)
    save(store,"benchmark.score",dict(id="obsolete",pipeline_id=p["id"],attempt_id=n["attempt_id"],reference_valid=True,result={"score":1}))
    result=leaderboard(store,"alice",family="pipeline")
    assert len(result["cohorts"])==1 and len(result["items"])==2
    assert result["items"][1]["score"]==0
    assert result["items"][0]["score_set_id"]=="p1:ss"

def test_development_and_rescored_reference_never_leak_into_official_board(store):
    pipeline(store,"p1",mode="development_reference")
    p,ss,n=pipeline(store,"p2","beta")
    ss["reference_overrides"]={n["id"]:dict(target="changed",reference_valid=True,reference_status="human_reviewed")}
    save(store,"benchmark.scoreset",ss)
    assert not leaderboard(store,"alice")["cohorts"]
    development=leaderboard(store,"alice",scope="development")
    assert len(development["items"])>=1 and development["cohorts"]

def test_api_auth_owner_scope_validation_and_read_only(accounts):
    workspace,admin,alice,bob=accounts
    store=alice.app.state.research["store"]
    qa(store,"a01")
    assert alice.get("/v1/evaluation/leaderboard").status_code==200
    assert alice.get("/v1/evaluation/leaderboard").json()["items"]
    assert not bob.get("/v1/evaluation/leaderboard").json()["items"]
    assert alice.get("/v1/evaluation/leaderboard?scope=invalid").status_code in [409,422]
    assert alice.get("/v1/evaluation/leaderboard?limit=101").status_code==422
    assert not workspace.repo.list("egress_audit")

def test_single_task_benchmark_f1_and_development_rescore_have_separate_boards(store):
    run,ss,node=pipeline(store,"base")
    task=store.get("benchmark.pipeline.task","base:bundle","alice")["tasks"][0]
    task.update(task_family="kie.extract",answer_kind="kie",input_hash="same-input")
    r=dict(id="b1",name="task score",status="completed",created_at=run["created_at"],mode="official_reviewed",
           release_hash="release",dataset_id="dataset",track="kie_image",tasks=[task],model=run["model"],max_calls=10,
           scorer_version="kie-vqa-score.v1",scorer_config={"threshold":.6},prompt={"sha256":"prompt"},method={"id":"E00"})
    save(store,"benchmark.run",r)
    save(store,"benchmark.attempt",dict(id="a1",run_id="b1",task_id="q",status="completed",response={"demo":False}))
    score=dict(id="s1",run_id="b1",attempt_id="a1",mode="official_reviewed",target_snapshot=task["target"],reference_status="human_reviewed",result={"score":.75},scorer_version=r["scorer_version"])
    save(store,"benchmark.score",score)
    value=leaderboard(store,"alice",family="benchmark")
    assert value["items"][0]["score"]==.75 and value["cohorts"][0]["metric"]=="detection_f1"
    save(store,"benchmark.score",dict(score,id="s2",mode="development_reference",result={"score":.5}))
    assert not leaderboard(store,"alice",family="benchmark")["items"]
    assert leaderboard(store,"alice",family="benchmark",scope="development")["items"][0]["score"]==.5

@pytest.mark.asyncio
async def test_real_evaluation_worker_records_feed_the_board(lab,monkeypatch):
    from test_research_products import release,drain
    from screenshotlegal.research.contracts import EvaluationCreate
    _,published=await release(lab,gold=True)
    model=dict(id="real-snapshot",config_id="real",name="Real transport fixture",model="model",endpoint="https://unit.test/v1",parameters={"temperature":0})
    monkeypatch.setattr(lab.gateway,"freeze",lambda *a,**k:model)
    async def call(*a,**k):return dict(raw="GOLD_SENTINEL",demo=False,usage=None,latency_ms=100)
    monkeypatch.setattr(lab.gateway,"call",call)
    run=lab.evaluation.create_run("alice",EvaluationCreate(name="worker integration",release_id=published["id"],model_ids=["real"],idempotency_key="leaderboard"))
    await drain(lab)
    row=leaderboard(lab.store,"alice")["items"][0]
    assert row["run_id"]==run["id"] and row["score"]==1
    assert row["planned"]==2 and row["eligible"]==1
