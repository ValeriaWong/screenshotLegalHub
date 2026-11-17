"""Offline source, provenance, image coverage, and local review-link checks."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import unquote,urlsplit
import copy,json,sys
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.v2_cause_batch import OUT,read,sha,normalize,save,processing_items


class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[];self.ids=set()
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if 'id' in attrs:self.ids.add(attrs['id'])
        for key in ('href','src'):
            if key in attrs:self.links.append(attrs[key])


def main():
    manifest=read(OUT/'manifest.json');assert len(manifest['representatives'])==207
    assert len({i['cause'] for i in manifest['representatives']})==207
    pool=[json.loads(line) for line in (OUT/'source_pool.jsonl').read_text(encoding='utf-8').splitlines()]
    assert len(pool)==350
    pool_by_index={i['source_index']:i for i in pool}
    rendered=[];images=quotes=0
    for item in processing_items(manifest):
        directory=OUT/'zh'/item['id'];s=read(directory/'source.json');p=pool_by_index[s['source_index']]
        assert sha(s['text'].encode('utf-8'))==s['judgment_text_sha256']==p['judgment_text_sha256']
        assert (directory/'judgment.txt').read_bytes()==s['text'].encode('utf-8')
        assert all(s['text'][seg['char_start']:seg['char_end']]==seg['text'] for seg in s['paragraphs'])
        if read(directory/'status.json')['phase']!='rendered':continue
        c=read(directory/'case.json');r=read(directory/'render.json');covered=set();fixed={};fragments={}
        assert not normalize(c,s)[1],(item['id'],normalize(c,s)[1])
        for m in c['messages']:
            for ref in m['source_refs']:assert s['text'][ref['char_start']:ref['char_end']]==ref['quote']
            if m['origin_type']=='verbatim_quote':
                assert any(m['text']==ref['quote'] for ref in m['source_refs']);quotes+=1
        for shot in r['images']:
            with Image.open(directory/shot['path']) as png:
                assert png.size==(860,1864)
                chrome=(png.crop((0,0,860,176)).tobytes(),png.crop((0,1738,860,1864)).tobytes())
                cid=shot['conversation_id']
                if cid in fixed:assert chrome==fixed[cid]
                else:fixed[cid]=chrome
            for box in shot['boxes']:
                x,y,w,h=box['bbox_pixels'];assert x>=0 and x+w<=860 and y>=176 and y+h<=1738
            if shot.get('scroll_fragment'):
                f=shot['scroll_fragment'];fragments.setdefault(f['message_id'],[]).append(f)
            covered.update(shot['message_ids']);images+=1
        assert covered=={m['id'] for m in c['messages']}
        for spans in fragments.values():
            spans.sort(key=lambda f:f['offset_css']);assert spans[0]['offset_css']==0
            assert all(b['offset_css']<=a['offset_css']+a['visible_height_css'] for a,b in zip(spans,spans[1:]))
            assert spans[-1]['offset_css']+spans[-1]['visible_height_css']>=spans[-1]['full_height_css']
        for q in read(directory/'questions.review.json'):assert set(q['message_ids'])<=covered
        rendered.append(item['id'])
    cache={};checked=0
    def parse(path):
        if path not in cache:
            h=Links();h.feed(path.read_text(encoding='utf-8'));cache[path]=h
        return cache[path]
    pages=[OUT/'index.html']+list(OUT.glob('zh/*/JUDGMENT.html'))+list(OUT.glob('zh/*/review.html'))
    for page in pages:
        for url in parse(page).links:
            parts=urlsplit(url)
            if parts.scheme or url.startswith('//'):continue
            target=(page.parent/unquote(parts.path)).resolve() if parts.path else page.resolve()
            assert target.exists(),(page,url)
            if parts.fragment and target.suffix=='.html':assert unquote(parts.fragment) in parse(target).ids,(page,url)
            checked+=1
    # Negative checks prevent apparently grounded but altered quotes and hidden evidence IDs.
    d=OUT/'zh/zh_0156';source=read(d/'source.json');candidate=read(d/'case.json')
    _,errors=normalize(candidate,source);assert not errors
    altered=copy.deepcopy(candidate);next(m for m in altered['messages'] if m['origin_type']=='verbatim_quote')['text']+='改'
    assert any('altered quote' in e for e in normalize(altered,source)[1])
    hidden=copy.deepcopy(candidate);hidden['questions'][0]['message_ids'].append('missing_hidden_message')
    assert any('missing message citation' in e for e in normalize(hidden,source)[1])
    invalid=copy.deepcopy(candidate);next(m for m in invalid['messages'] if m['kind']=='transfer')['transfer']['amount']=-1
    assert any('invalid transfer amount' in e for e in normalize(invalid,source)[1])
    unsupported=copy.deepcopy(candidate);next(m for m in unsupported['messages'] if m['kind']=='transfer')['transfer']['receipt_status']='received'
    assert any('receipt status missing source support' in e for e in normalize(unsupported,source)[1])
    invalid_span=copy.deepcopy(candidate)
    invalid_span['messages'][0]['source_refs'][0]['char_end']+=1
    assert any('invalid explicit source coordinates' in e for e in normalize(invalid_span,source)[1])
    # Repeated short quotes must retain the context-reviewed occurrence.
    repeated_source=read(OUT/'zh/zh_0145/source.json')
    repeated_case=read(OUT/'zh/zh_0145/case.json')
    ref=next(m for m in repeated_case['messages'] if m['id']=='m010')['source_refs'][0]
    assert repeated_source['text'][ref['char_start']-5:ref['char_end']+1]=='张某雪称“对”'
    normalized,errors=normalize(repeated_case,repeated_source);assert not errors
    preserved=next(m for m in normalized['messages'] if m['id']=='m010')['source_refs'][0]
    assert preserved['char_start']==ref['char_start']
    result={'source_records':350,'representative_sources_verified':207,'supplemental_sources_verified':len(manifest.get('supplemental_representatives',[])),'rendered_case_ids':rendered,
            'rendered_images_checked':images,'exact_messages_checked':quotes,'local_links_checked':checked,
            'negative_provenance_checks':5,'repeated_quote_coordinate_preservation':True,'human_quality_review':False,'difficulty_certified':False}
    save(OUT/'verification.json',result);print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');main()
