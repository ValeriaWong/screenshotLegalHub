"""Run pinned author components with explicit SDK, model and optional format adaptations."""
import argparse
import json
import os
from pathlib import Path
import sys

REPO=Path(__file__).resolve().parents[3]
UPSTREAM=REPO/'paper/upstream_sources/self_refine'
DEPENDENCY=REPO/'paper/upstream_sources/prompt_lib'
sys.path[:0]=[str(UPSTREAM),str(DEPENDENCY)]
# prompt-lib constructs an unused Anthropic client during import. Its 2023
# positional API key call needs this compatibility shim with anthropic 0.3.11.
import anthropic
original_anthropic_client=anthropic.Client
anthropic.Client=lambda api_key=None,**kwargs:original_anthropic_client(api_key=api_key,**kwargs)
from src import utils
# Preserve the author algorithm, but forbid automatic whole-run paid retries.
utils.retry_parse_fail_prone_cmd=lambda function,**kwargs:function
from src.acronym.task_init import AcronymGenTaskInit
from src.acronym.task_iterate import AcronymGenTaskIterate
from src.acronym.feedback import AcronymGenFeedback
from src.acronym.run import iterative_acronym
from prompt_lib.backends import openai_api
import openai

TITLE='Using language models of code for few-shot commonsense'

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True);parser.add_argument('--execute',action='store_true');parser.add_argument('--one-revision',action='store_true')
    args=parser.parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    os.chdir(UPSTREAM)
    init=AcronymGenTaskInit('data/prompt/acronym/init.jsonl','gpt-3.5-turbo')
    feedback=AcronymGenFeedback('gpt-3.5-turbo','data/prompt/acronym/feedback.jsonl')
    revise=AcronymGenTaskIterate('gpt-3.5-turbo','data/prompt/acronym/feedback.jsonl')
    plan=dict(native_entrypoint='src.acronym.run.iterative_acronym',input_title=TITLE,max_attempts=2,max_model_requests=4,
              author_engine_alias='gpt-3.5-turbo',actual_model='DeepSeek-V4.1-Flash-1017',
              initial_prompt=init.make_query(TITLE),feedback_prompt_template=feedback.prompt,revision_prompt_template=revise.prompt,
              source_changed=False,changes=['Anthropic constructor keyword shim for unused import','disable automatic parse-failure retry','OpenAI SDK API base routed to budgeted localhost broker; real backend is DeepSeek'])
    if args.one_revision:
        plan.update(native_entrypoint='AcronymGenTaskInit -> AcronymGenFeedback -> AcronymGenTaskIterate',max_attempts=None,max_model_requests=3,final_feedback_not_run=True)
        plan['changes'].append('Original chat engine alias retained in SDK response; actual DeepSeek identity retained in broker trace')
        plan['changes'].append('Task-format guidance appended to the system message; original few-shot prompt text retained')
    (out/'native_plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    if not args.execute:
        print(json.dumps(dict(status='original_prompts_built',model_requests=0)));return
    openai.api_base=os.environ['AUTHOR_REPRO_BROKER_URL']
    openai.api_key=os.environ['AUTHOR_REPRO_BROKER_TOKEN']
    # Record an original SDK request without changing the author's prompts/parsers.
    def no_extra_engines(**kwargs):
        if kwargs.get('model')!='gpt-3.5-turbo':raise RuntimeError('Unexpected native engine')
        return original_create(**kwargs)
    original_create=openai.ChatCompletion.create
    openai.ChatCompletion.create=no_extra_engines
    # The original function writes one diagnostic prompt in its cwd. Redirect
    # only that known filename to this run directory; preserve author sources.
    import builtins
    original_open=builtins.open
    def scoped_open(file,*values,**keywords):
        if isinstance(file,str) and file.startswith('acronym_iterate_') and file.endswith('.txt'):
            file=out/file
        return original_open(file,*values,**keywords)
    builtins.open=scoped_open
    if args.one_revision:
        acronym=init(title=TITLE)
        feedback_text=feedback(title=TITLE,acronym=acronym)
        new_title,new_acronym=revise(acronyms_to_scores={acronym:(TITLE,feedback_text)})
        result=dict(title=TITLE,initial_acronym=acronym,feedback=feedback_text,revised_title=new_title,revised_acronym=new_acronym,author_components=['AcronymGenTaskInit','AcronymGenFeedback','AcronymGenTaskIterate'],final_feedback_not_run=True)
    else:
        result=iterative_acronym(title=TITLE,max_attempts=2)
    (out/'native_output.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(status='original_author_modules_completed_one_revision' if args.one_revision else 'original_controller_completed',items=len(result),model_identity_substituted=True)))

if __name__=='__main__':main()
