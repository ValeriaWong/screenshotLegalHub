"""L-MAD (Nguyen et al., 2026), https://arxiv.org/html/2607.09099v1.
Reproduction: paper-defined scheduler + unchanged selected MALLM components;
NOT verified L-MAD author code and NOT original Qwen/Llama checkpoint inference.
Original task: relevant Japanese Civil Code premise(s) + hypothesis -> Answer:Y/N.
Benchmarks: COLIEE Task 4 R05/R06/R07 (109/73/82 samples); accuracy, parsed label.
Innovation: compare neutral three-persona debate, threshold/hybrid consensus vs
fixed-horizon ranked voting; restrict context to two recent turns, retain splits.
Original native input/output: statutory text + legal proposition -> binary label
and brief explanation. Our native fixture is the paper's English Article9 example,
not a released COLIEE evaluation subset. DeepSeek API replaces original local models.
Executed upstream components: SimpleResponseGenerator.get_filled_template,
ResponseGenerator.extract_agreement/ranking prompts, ThresholdConsensus.make_decision,
RankedVoting.process_votes/process_results. Their original bodies are not rewritten.
Generation cap 1024 is our bounded setting; the paper does not specify that cap.
Our scheduler freezes each round's two prior complete rounds; fixed Appendix A.1
personas replace undocumented automatic persona regeneration. Hybrid threshold is
configured from L-MAD (unanimity until last round, then .66), not MALLM's different
HybridMajority default (.75, turn5, <=3 agents => always unanimity).
Main Answer:Y/N parser stays separate from Appendix 判断:Y/N; raw format conflicts
remain visible. Ranked ballots must be full permutations as the paper specifies;
MALLM's ten paid parse retries are not invoked. One tie round, then unknown if tied.
Product mapping: text-only entailment can verify evidence statements and binary
VQA hypotheses. Non-entailment is not proof of the opposite, so product labels
require separate positive entailment checks; neither/both supported => unknown.
Pixel KIE and general open legal reasoning are not native outputs of this method.
All prompts, ballots, agreement windows, parse failures and unknowns are recorded.
"""
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
from types import SimpleNamespace
from mallm_components import load
HERE=Path(__file__).parent


def parse_label(text,appendix=False):
    key='判断' if appendix else 'Answer'
    found=re.findall(r'(?m)^\s*(?:Final Solution:\s*)?'+key+r'\s*[:：]\s*([YN])\b',text)
    return found[0] if len(found)==1 else None


def run(request,generate):
    specification=json.loads((HERE/'specification.lock.json').read_text(encoding='utf-8'))
    for file,expected in specification['files'].items():
        if hashlib.sha256((HERE/file).read_bytes()).hexdigest()!=expected:raise ValueError('Pinned L-MAD evidence changed: '+file)
    originals,upstream=load()
    protocol=request.get('protocol','hybrid');round_cap=request.get('rounds',3)
    if protocol not in ('hybrid','majority','supermajority','unanimity','ranked') or round_cap not in (1,2,3):raise ValueError('Unsupported L-MAD protocol/round cap')
    prompts=json.loads((HERE/'paper_prompts.json').read_text(encoding='utf-8'))
    people=request.get('personas') or prompts['personas']
    if len(people)!=3:raise ValueError('This replication fixes three personas; other population ablations not reproduced')
    panelists=[SimpleNamespace(id=str(i),short_id=str(i),persona=p['name'],persona_description=p['description']) for i,p in enumerate(people)]
    instruction=request.get('task_instruction','Decide whether the supplied premise legally entails the hypothesis. Evaluate peers neutrally. End with exactly one line Answer:Y or Answer:N and give a brief public explanation, not hidden reasoning.')
    source_input=json.dumps(dict(premise=request['premise'],hypothesis=request['hypothesis']),ensure_ascii=False)
    records=[];agreements=[];agreement_log=[];calls=0;last_label=None;last_draft=None;ranking_rounds=[]
    parameters=dict(temperature=.1,max_tokens=request.get('max_output_tokens',1024))
    def invoke(stage,messages):
        nonlocal calls
        if calls>=request.get('max_calls',100):raise ValueError('Per-unit call bound reached before model request')
        calls+=1
        result=generate(stage,messages,parameters)
        if not isinstance(result,str) or not result.strip():raise ValueError('Empty or non-text model response')
        return result
    threshold=1.0 if protocol=='unanimity' else .5 if protocol=='majority' else .66
    consensus=originals.ThresholdConsensus(panelists,0,None,threshold_percent=threshold,
        threshold_turn=round_cap if protocol=='hybrid' else None,threshold_agents=None)
    ranked=originals.RankedVoting(panelists,0,None,vote_turn=round_cap)
    final_label=None;decision=False;decision_reason='round_limit_without_consensus';latest={};completed_round=0
    # At most one supplementary full round exists, and only after a tied terminal vote.
    maximum_rounds=round_cap+1 if protocol=='ranked' else round_cap
    for round_index in range(1,maximum_rounds+1):
        if round_index>round_cap and (not ranking_rounds or ranking_rounds[-1]['agreed']):break
        visible_records=[r for r in records if round_index-2<=r['round']<round_index]
        memory=[dict(role='user',content='Round '+str(r['round'])+' '+r['persona']+':\n'+r['raw']) for r in visible_records]
        frozen_draft=last_draft
        for agent_index,panelist in enumerate(panelists):
            current_draft=latest.get(panelist.id,{}).get('raw') if protocol=='ranked' else frozen_draft
            data=originals.TemplateFilling(task_instruction=instruction,input_str=source_input,current_draft=current_draft,
                persona=panelist.persona,persona_description=panelist.persona_description,agent_memory=memory)
            messages=originals.SimpleResponseGenerator.get_filled_template(data)
            messages.append(dict(role='user',content=('Propose your own solution.' if not current_draft else
                'Evaluate the available evidence neutrally. Signal [AGREE] or [DISAGREE] with the current solution; revise if needed.')+
                ' Always give exactly one final Answer:Y or Answer:N line. Do not quote other Answer lines.'))
            stage='round.'+str(round_index)+'.agent.'+panelist.id
            raw=invoke(stage,messages);label=parse_label(raw)
            entry=dict(round=round_index,agent_id=panelist.id,persona=panelist.persona,raw=raw,label=label,
                visible_message_ids=[r['message_id'] for r in visible_records],message_id=len(records),stage=stage)
            records.append(entry);latest[panelist.id]=entry
            if label is None:raise ValueError('Strict Answer:Y/N parser rejected response at '+stage)
            signal=originals.ResponseGenerator.extract_agreement(raw,not bool(current_draft))
            # Upstream consensus expects blank solution for an agreement and a full
            # solution for a new draft. Do not count a contradictory label as assent.
            agrees=bool(signal is True and label==last_label)
            solution='' if agrees else 'Answer:'+label
            agreement=originals.Agreement(agreement=True if agrees else None if not current_draft else False,
                response=raw,solution=solution,agent_id=panelist.id,persona=panelist.persona,message_id=entry['message_id'])
            agreements.append(agreement)
            if solution:last_label=label;last_draft=raw
            entry['raw_agreement_signal']=signal;entry['normalized_agreement']=agrees
            if protocol!='ranked':
                candidate,agreed,agreements,_,_=consensus.make_decision(agreements,round_index,agent_index,instruction,source_input,SimpleNamespace())
                agreement_log.append(dict(stage=stage,candidate=candidate,agreed=agreed,window=[asdict(a) for a in agreements],
                    threshold='unanimity' if protocol=='hybrid' and round_index<round_cap else threshold))
                if agreed:
                    final_label=parse_label(candidate);decision=final_label is not None;decision_reason='consensus_threshold';break
        completed_round=round_index
        if decision:break
        if protocol=='ranked' and round_index>=round_cap:
            answers=[latest[p.id]['raw'] for p in panelists]
            votes=[];vote_log=[];process_log=''
            for panelist in panelists:
                messages=originals.ResponseGenerator.generate_ranking_prompt(panelist,panelists,instruction,source_input,answers)
                messages.append(dict(role='user',content='Rank every candidate exactly once; return a complete permutation of 0 1 2. No explanation.'))
                raw=invoke('vote.'+str(round_index)+'.agent.'+panelist.id,messages)
                try:permutation=[int(v) for v in raw.strip().split()]
                except ValueError:raise ValueError('Rank ballot is not an integer permutation; no automatic retry') from None
                if sorted(permutation)!=list(range(3)):raise ValueError('Rank ballot must contain every candidate exactly once; no automatic retry')
                _,votes,valid,process_log=ranked.process_votes(answers,panelist,raw,votes,process_log)
                if not valid:raise ValueError('Original ranked vote parser rejected ballot')
                vote_log.append(dict(agent_id=panelist.id,raw=raw,ranking=permutation))
            result=ranked.process_results({},originals.DecisionAlteration.ANONYMOUS,answers,votes)['anonymous']
            ranking_rounds.append(dict(round=round_index,ballots=vote_log,candidates=answers,original_result=asdict(result),agreed=result.agreed))
            if result.agreed:
                final_label=parse_label(result.final_answer);decision=final_label is not None;decision_reason='ranked_borda_winner';break
            decision_reason='rank_tie_after_one_supplement' if round_index>round_cap else 'rank_tie_requires_supplement'
    return dict(method='l_mad',protocol=protocol,output={'answer':final_label,'decision':decision,'reason':decision_reason},
        records=records,agreement_checks=agreement_log,ranking_rounds=ranking_rounds,calls=calls,completed_rounds=completed_round,
        source_kind='paper_specification_with_cited_upstream_components',LMAD_author_code_executed=False,
        upstream_component_code_executed=True,upstream_commit=upstream['commit'],local_model_inference=False,
        native_benchmark_scope=request.get('scope','task_adaptation'),original_complete_benchmark=False)
