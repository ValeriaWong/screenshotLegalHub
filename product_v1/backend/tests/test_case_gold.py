import importlib.util
from pathlib import Path
import pytest
from screenshotlegal.experiments.gold import CaseGold,score_result
from screenshotlegal.research.contracts import digest


def fixture():
    output=dict(summary='fixture',claims=[dict(id='c',label='请求A',applicability='plausible',fact_ids=['f'])],elements=[dict(id='e',label='要件A',claim_id='c',fact_ids=['f'],burden_role='claimant',burden_origin='model_inferred')],facts=[dict(id='f',statement='record',citations=[dict(source_ref_id='s',quote='x',start=0,end=1)])])
    run=dict(status='completed',demo=False,input_digest='input',case_group_id='g',split='holdout',output=output,output_digest=digest(output),template_fields_provided=False)
    result=dict(run=run,input_manifest=dict(source_file_hashes=['sha']))
    gold=CaseGold(case_group_id='g',input_digest='input',source_file_hashes=['sha'],split='holdout',status='adjudicated',reviewers=['synthetic-reviewer-a','synthetic-reviewer-b'],reviewed_at='synthetic-fixture-only',claims_complete=True,claims=[dict(label='请求A',applicability='plausible')],burdens=[dict(element_label='要件A',role='claimant')],citation_judgments=[dict(output_digest=run['output_digest'],fact_id='f',citation_index=0,supported=False)])
    return result,gold


def test_gold_separates_exact_spans_from_human_semantic_support_and_template_burdens():
    result,gold=fixture();score=score_result(result,gold)
    assert score['metrics']==dict(claim_label_set_f1=1,burden_accuracy=1,citation_support_accuracy=0)
    result['run']['template_fields_provided']=True
    assert score_result(result,gold)['metrics']['burden_accuracy'] is None
    result['run']['demo']=True
    assert all(v is None for v in score_result(result,gold)['metrics'].values())


def test_gold_binding_partial_labels_and_review_provenance():
    result,gold=fixture()
    assert score_result(result,gold.model_copy(update={'input_digest':'different'}))['reason']=='gold_binding_mismatch'
    assert score_result(result,gold.model_copy(update={'claims_complete':False}))['metrics']['claim_label_set_f1'] is None
    with pytest.raises(ValueError):CaseGold.model_validate(gold.model_dump()|dict(reviewers=[]))
    with pytest.raises(ValueError):CaseGold.model_validate(gold.model_dump()|dict(claims=[dict(label='A',aliases=['A'],applicability='plausible')]))


def test_paired_report_excludes_unmatched_models_and_collapses_case_groups():
    path=Path(__file__).resolve().parents[3]/'paper/experiments/report.py'
    spec=importlib.util.spec_from_file_location('paper_report',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    rows=[]
    for group,difference in [('g1',.2),('g2',.4)]:
        for repeat in range(2):
            for method,value in [('E03',.3),('E11',.3+difference)]:
                rows.append(dict(case_group_id=group,case_id=group,repeat=repeat,method_id=method,scoring=dict(metrics=dict(score=value)),result=dict(run=dict(demo=False,model_revision_declared='m1',response_models=['m1'],input_digest=group,model_digest='m',budget={},split='holdout',protocol_digest='v',method_options={}),staleness=dict(stale=False))))
    result=module.paired_bootstrap(rows,'E03','E11','score')
    assert result['paired_case_groups']==2 and result['mean_difference']==pytest.approx(.3)
    for row in rows:
        if row['method_id']=='E11':row['result']['run']['response_models']=['m2']
    assert module.paired_bootstrap(rows,'E03','E11','score')['paired_case_groups']==0
