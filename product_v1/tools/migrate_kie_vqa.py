"""Import an audited legacy snapshot into the owner-scoped research store, without model calls."""
import argparse,json
from pathlib import Path
from screenshotlegal.research.store import Store
from screenshotlegal.research.benchmark_import import import_legacy
from screenshotlegal.research.benchmark import Benchmark,DEFAULTS
from screenshotlegal.research.contracts import now
from screenshotlegal.research import audit

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--preparation',required=True);p.add_argument('--workspace',required=True);p.add_argument('--data-dir',required=True);p.add_argument('--owner',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();store=Store(a.data_dir);benchmark=Benchmark(store)
    token=audit.context.set(dict(actor_id=a.owner,actor_type='user',product='evaluation',correlation_id='kie-vqa-migration-20261024',request_id='local-migration-20261024'))
    try:
        d=import_legacy(store,a.owner,a.source,a.preparation,a.workspace)
        prompts=[]
        for family,markdown in DEFAULTS.items():
            existing=next((r for r in benchmark.prompts(a.owner) if r['name']=='迁移初始模板' and r['family']==family),None)
            prompts.append(existing or benchmark.save_prompt(a.owner,dict(name='迁移初始模板',family=family,parent_id=None,markdown=markdown,note='新输入契约初版；旧问句单独归档，不用于新视觉运行',idempotency_key='initial:'+d['id']+family)))
        replay=benchmark.replay(a.owner,d['id'],dict(idempotency_key='migration-replay:'+d['id']))
        summary=dict(dataset_id=d['id'],counts=d['counts'],replay_run_id=replay['id'],replay_counts=replay['counts'],prompt_ids=[r['id'] for r in prompts],new_model_calls=0,human_certifications=0,official_releases=0,created_at=now())
        dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(summary,ensure_ascii=False))
    finally: audit.context.reset(token)
if __name__=='__main__': main()
