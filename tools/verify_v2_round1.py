"""Offline source/PNG/provenance/link integrity check and consolidated exports."""
from pathlib import Path
import sys
import json
import re
from html.parser import HTMLParser
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from legalhub.synthesis import settings,read,write,digest,validate


class Links(HTMLParser):
    def __init__(self):super().__init__();self.paths=[]
    def handle_starttag(self,tag,attrs):
        for key,value in attrs:
            if key in ['src','href'] and value and not re.match(r'^(?:https?:|#)',value):self.paths.append(value)


def main():
    cfg,out=settings();source_hashes={};questions=[];tasks=[];cases=[]
    count={'cases':0,'messages':0,'conversations':0,'screenshots':0,'questions':0,
           'verbatim_quotes':0,'multi_image_candidate_questions':0,'cross_conversation_candidate_questions':0}
    final_files=[]
    for spec in cfg['cases']:
        folder=out/spec['language']/spec['id'];source=read(folder/'source.json');candidate=read(folder/'curated.json')
        checks=validate(candidate,source);assert checks['passed'],checks['errors']
        name=source['source_file']
        if name not in source_hashes:source_hashes[name]=digest((ROOT/name).read_bytes())
        assert source_hashes[name]==source['source_sha256'],'Original source changed'
        assert digest(source['text'].encode('utf-8'))==source['judgment_text_sha256']
        for p in source['paragraphs']:assert source['text'][p['char_start']:p['char_end']]==p['text']
        render=read(folder/'render.json');qs=read(folder/'questions.review.json')
        mids=[b['message_id'] for im in render['images'] for b in im['messages']]
        assert len(mids)==len(set(mids))==len(candidate['messages'])
        assert set(mids)=={m['id'] for m in candidate['messages']}
        for im in render['images']:
            path=folder/im['file'];assert digest(path.read_bytes())==im['sha256']
            with Image.open(path) as png:assert png.size==(540,960);png.verify()
            for b in im['messages']:
                l,t,r,bt=b['bbox'];assert 0<=l<r<=540 and 0<=t<bt<=960
        for q in qs:
            mentioned=set(re.findall(r'\bm\d{3}\b',q['answer']+' '+' '.join(q['reasoning_steps'])))
            assert mentioned<=set(q['minimal_message_ids'])
            questions.append({'case_id':spec['id'],'language':spec['language'],**q})
            count['multi_image_candidate_questions']+=int(q['proposed_required_image_count']>1)
            count['cross_conversation_candidate_questions']+=int(q['proposed_required_conversation_count']>1)
        for task in read(folder/'tasks.image_only.json'):
            assert 'answer' not in task and 'facts' not in task
            tasks.append({**task,'images':[(folder/p).relative_to(out).as_posix() for p in task['images']]})
        count['cases']+=1;count['messages']+=len(candidate['messages']);count['conversations']+=len(candidate['conversations'])
        count['screenshots']+=len(render['images']);count['questions']+=len(qs)
        count['verbatim_quotes']+=sum(m['origin_type']=='verbatim_quote' for m in candidate['messages'])
        cases.append({'id':source['id'],'language':source['language'],'cause':source['cause'],
                      'source':(folder/'source.json').relative_to(out).as_posix(),
                      'judgment_sha256':source['judgment_text_sha256'],'candidate':candidate,
                      'render':render,'status':'development_human_review_pending'})
        for file in ['curated.json','curation.json','render.json','questions.review.json','tasks.image_only.json','source.json']:
            path=folder/file;final_files.append({'file':path.relative_to(out).as_posix(),'sha256':digest(path.read_bytes())})
    for page in [out/'index.html',*out.glob('*/*/review.html')]:
        parser=Links();parser.feed(page.read_text(encoding='utf-8'))
        for path in parser.paths:assert (page.parent/path).is_file(),(page,path)
    for name,rows in [('cases.jsonl',cases),('questions.review.jsonl',questions),('tasks.image_only.jsonl',tasks)]:
        (out/name).write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in rows),encoding='utf-8')
    result={'check':'passed','counts':count,'source_hashes_unchanged':source_hashes,
            'final_files':final_files,'model_requests':0,
            'limits':'Does not certify legal fidelity, minimal evidence necessity or benchmark difficulty. Candidate count statistics only.'}
    write(out/'verification.json',result)
    print(json.dumps({'check':'passed','counts':count,'model_requests':0},ensure_ascii=False))


if __name__=='__main__':main()
