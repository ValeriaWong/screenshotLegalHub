import copy
import pytest
from screenshotlegal.research.leaderboard import leaderboard
from screenshotlegal.research.leaderboard_taxonomy import entry_metadata
from test_leaderboard import store,save,qa,pipeline
from test_accounts_ingestion import accounts

def benchmark(store,id,method,model="alpha",score=1,**updates):
    m=dict(id=id+":model",config_id=model,name=model.title(),model="model-"+model,endpoint="https://unit.test/v1",parameters={"temperature":0})
    task=dict(task_id="q",task_family="vqa.field",answer_kind="text",label="content",target="frozen gold",input_hash="same-input",source_task_hash="same-source",reference_status="human_reviewed")
    run=dict(id=id,name=id,status="completed",created_at="2026-10-29T10:00:"+id[-2:]+"+00:00",mode="official_reviewed",
        dataset_id="dataset",release_hash="release",track="vqa_image_full",tasks=[task],model=m,max_calls=100,
        scorer_version="kie-vqa-score.v1",scorer_config={"threshold":.6},prompt={"sha256":"shared-base-prompt"},method=method,method_max_output_tokens=6144)
    run.update(updates);save(store,"benchmark.run",run)
    save(store,"benchmark.attempt",dict(id=id+":attempt",run_id=id,task_id="q",status="completed",response={"demo":False}))
    save(store,"benchmark.score",dict(id=id+":score",run_id=id,attempt_id=id+":attempt",mode="official_reviewed",
        reference_status="human_reviewed",target_snapshot=task["target"],scorer_version=run["scorer_version"],result={"score":score}))
    return run

REACT=dict(id="E01",name="ReAct",author_controller="webthink",attempts=2)
REFINE=dict(id="E05",name="Self-Refine",author_controller="iterative_response",attempts=2)

def test_four_categories_and_cross_tags_are_from_execution_metadata(store):
    qa(store,"a01")
    p,ss,n=pipeline(store,"p1")
    n["variant"]="reference_guided_prediction";save(store,"benchmark.pipeline.node",n)
    benchmark(store,"b02",REACT)
    benchmark(store,"b03",REFINE)
    assert leaderboard(store,"alice",category="oneshot")["items"][0]["model"]["name"]=="Alpha"
    enhanced=leaderboard(store,"alice",category="kie_enhanced")["items"]
    assert enhanced and all(r["categories"]==["kie_enhanced"] for r in enhanced)
    agents=leaderboard(store,"alice",category="agent")["items"]
    assert len(agents)==1 and agents[0]["method"]["id"]=="E01"
    assert set(agents[0]["categories"])=={"agent","reproductions"}
    board=leaderboard(store,"alice",category="reproductions",comparison="methods")
    assert len(board["cohorts"])==1
    assert {r["method"]["id"] for r in board["items"]}=={"E01","E05"}
    assert {c["id"] for c in board["categories"]}=={"oneshot","kie_enhanced","agent","reproductions"}

def test_standalone_kie_extraction_is_not_kie_enhanced(store):
    p,ss,n=pipeline(store,"p1");n["variant"]="kie_image";save(store,"benchmark.pipeline.node",n)
    assert not leaderboard(store,"alice",category="kie_enhanced")["items"]
    assert leaderboard(store,"alice",category="oneshot")["items"]

def test_method_comparison_fixes_bottom_model_and_keeps_methods_and_versions(store):
    benchmark(store,"a01",REACT,score=1)
    benchmark(store,"a02",REFINE,score=0)
    benchmark(store,"a03",REFINE,score=.5)
    benchmark(store,"a04",REFINE,model="beta",score=1)
    board=leaderboard(store,"alice",category="reproductions",comparison="methods")
    assert len(board["cohorts"])==2
    alpha=next(c for c in board["cohorts"] if c["fixed_model_name"]=="Alpha")
    rows=leaderboard(store,"alice",category="reproductions",comparison="methods",cohort_id=alpha["id"])["items"]
    assert len(rows)==2 and len({r["entry_id"] for r in rows})==2
    refine=next(r for r in rows if r["method"]["id"]=="E05")
    assert refine["run_id"]=="a03" and refine["score"]==.5 and refine["repeated_runs"]==2
    assert len(leaderboard(store,"alice",category="reproductions",comparison="models")["cohorts"])==2

def test_method_controls_stay_fixed_and_baseline_only_joins_matching_method_cohort(store):
    benchmark(store,"a01",REACT)
    benchmark(store,"a02",{"id":"E00","name":"One-shot"})
    benchmark(store,"a03",{"id":"E00","name":"One-shot"},release_hash="other-release")
    result=leaderboard(store,"alice",category="reproductions",comparison="methods",include_baseline=True)
    assert len(result["cohorts"])==1 and len(result["items"])==2
    assert any(r["baseline"] and r["method"]["id"]=="E00" for r in result["items"])
    benchmark(store,"a04",REFINE,max_calls=20)
    assert len(leaderboard(store,"alice",category="reproductions",comparison="methods")["cohorts"])==2

def test_names_do_not_fabricate_category_and_empty_agent_is_not_filled_with_baselines(store):
    benchmark(store,"a01",{"id":"UNKNOWN","name":"ReAct KIE Agent paper"})
    assert not leaderboard(store,"alice",category="reproductions")["items"]
    assert not leaderboard(store,"alice",category="agent")["items"]
    qa(store,"a02")
    result=leaderboard(store,"alice",category="agent",comparison="methods",include_baseline=True)
    assert not result["cohorts"] and not result["summary"]["available_scopes"]

def agent(store,id,method_id="E02",case="case-a",config="alpha",**updates):
    m={"E00":dict(id="E00",name="One-shot",implementation="single_shot"),
       "E02":dict(id="E02",name="分阶段",implementation="staged_no_pack"),
       "E06":dict(id="E06",name="Verifier",implementation="independent_context_verifier",paper_sources=["https://example.test/paper"],reproduction_level="project_mechanism")}[method_id]
    m.update(implementation_digest="code",registry_digest="registry")
    row=dict(id=id,case_id=case,case_title="Private case "+case,name=id,case_group_id=case,split="development",
        model=dict(config_id=config,name=config.title(),model="model-"+config,endpoint="https://unit.test/v1",parameters={"temperature":0},billing={"currency":"CNY"}),
        method=m,protocol_digest="protocol",input_digest="frozen-input",perception_digest="perception",matterpack_digest="matter",legal_corpus_digest="law",
        budget={"max_model_calls":8,"max_tool_calls":8},method_options={"refinement_rounds":2},response_models=["model-"+config],model_revision_declared="model-"+config,
        status="completed",created_at="2026-10-29T10:00:00+00:00",usage=dict(model_calls=3,tool_calls=2,input_tokens=100,output_tokens=30,cost=.01,cost_recorded=3,missing_usage_calls=0,elapsed_ms=2300),
        output={"summary":"private output"},engineering_metrics={"quote_spans_validated":4})
    row.update(updates);save(store,"agent.run",row)
    return row

def test_agent_without_expert_gold_has_engineering_comparison_not_fake_quality(store):
    agent(store,"agent1")
    agent(store,"agent2","E06")
    agent(store,"agent0","E00")
    board=leaderboard(store,"alice",scope="development",category="agent",comparison="methods",include_baseline=True,case_access=lambda _:True)
    assert len(board["items"])==3 and len(board["cohorts"])==1
    assert all(r["rank"] is None and r["score"] is None for r in board["items"])
    assert all(r["eligible"]==0 and r["model_calls"]==3 and r["tool_calls"]==2 and r["elapsed_ms"]==2300 for r in board["items"])
    assert all("专家金标" in r["unranked_reason"] for r in board["items"])
    assert all("agent_run=" in r["href"] for r in board["items"])
    assert not leaderboard(store,"alice",scope="official",category="agent",case_access=lambda _:True)["cohorts"]

def test_agent_access_is_checked_even_for_owned_records_and_frozen_code_is_visible(store):
    agent(store,"visible")
    agent(store,"hidden",case="case-b",input_digest="different-input")
    def access(cid):
        if cid=="case-b":raise KeyError("case access revoked")
    result=leaderboard(store,"alice",scope="development",category="agent",case_access=access,agent_versions={"implementation_digest":"new-code","registry_digest":"registry"})
    assert len(result["items"])==1 and result["items"][0]["stale_code"]
    assert "case-b" not in str(result)
    assert not leaderboard(store,"alice",scope="development",category="agent")["items"]

def test_agent_api_uses_current_case_acl_and_category_parameters(accounts):
    w,admin,alice,bob=accounts
    cid=alice.post("/v1/cases",json={"title":"Agent board"}).json()["id"]
    store=alice.app.state.research["store"]
    agent(store,"a",case=cid)
    response=alice.get("/v1/evaluation/leaderboard?scope=development&category=agent&comparison=methods")
    assert response.status_code==200,response.text
    assert len(response.json()["items"])==1
    assert not bob.get("/v1/evaluation/leaderboard?scope=development&category=agent&comparison=methods").json()["items"]
    assert alice.get("/v1/evaluation/leaderboard?category=invalid").status_code in [409,422]
