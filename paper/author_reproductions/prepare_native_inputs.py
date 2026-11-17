"""Freeze original public task examples; no model calls and no target-based selection."""
import csv
import hashlib
import json
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).parent/'native_inputs'

def save(name,value):
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def main():
    with (ROOT/'paper/upstream_sources/solar_legalbench/data/sara_numeric/train.tsv').open(encoding='utf-8') as f:row=next(csv.DictReader(f,delimiter='\t'))
    save('solar',dict(input=dict(mode='native',description=row['description'],question=row['question']),reference=row['answer'],
        source=dict(repository='https://huggingface.co/datasets/nguha/legalbench',commit='e042ea68c19df12b737fe768572f22ead61e8e37',path='data/sara_numeric/train.tsv',row=0,case_id=row['case id']),selection='first train example; no target-based selection'))
    court=ROOT/'paper/upstream_sources/agentscourt/data/SimuCourt(1).json'
    row=json.loads(court.read_text(encoding='utf-8'))[0]
    keys=['案件名','基本案情','类别','原告（公诉）','被告','被告基本情况','原告诉请判令（公诉机关指控）','被告代理人辩护','被告陈述']
    save('agentscourt',dict(input=dict(case={k:row[k] for k in keys},turns=4),source=dict(commit='7c14d6960abfdfdd7366250905da8dbcb416d6d6',path='data/SimuCourt(1).json',row=0),selection='first original case; input whitelist excludes judgment labels'))
    save('raptor',dict(input=dict(mode='native',documents=[dict(id='author:demo/sample.txt',text=(ROOT/'paper/upstream_sources/raptor/demo/sample.txt').read_text(encoding='utf-8'))],question='How did Cinderella reach her happy ending?',chunk_tokens=200,num_layers=3,reduction_dimension=2),
        source=dict(commit='7da1d48a7e1d7dec61a63c9d9aae84e2dfaa5767',path='demo/sample.txt'),
        parameter_adaptation='Maximum 3 summary layers, reduction dimension 2, 200-token chunks to exercise recursive clustering on the full small author demo; original defaults 5 layers, dimension 10, 100-token chunks. Previous default-dimension run produced only one summary layer and is retained.'))
    cache=ROOT/'paper/.data/ultradomain';cache.mkdir(parents=True,exist_ok=True)
    revision='aa8a51d523f8fc3c5a0ab90dd16b7f6b9dbb5d0d';data=cache/'legal.jsonl'
    url=f'https://huggingface.co/datasets/TommyChien/UltraDomain/resolve/{revision}/legal.jsonl'
    if not data.exists():
        with requests.get(url,stream=True,timeout=(15,45)) as response:
            response.raise_for_status()
            with data.with_suffix('.part').open('wb') as out:
                for chunk in response.iter_content(1024*1024):out.write(chunk)
        data.with_suffix('.part').replace(data)
    with data.open(encoding='utf-8') as f:
        rows=[json.loads(line) for line in f if line.strip()]
    # Full context, not an answer-selected excerpt. Keep indexing within the explicit request cap.
    eligible=[(i,r) for i,r in enumerate(rows) if 5000<=len(r['context'])<=150000]
    if not eligible:raise ValueError('No full UltraDomain legal document fits the frozen development resource bound')
    i,row=eligible[0]
    save('lightrag',dict(input=dict(mode='native',documents=[dict(id='ultradomain:'+row.get('context_id',str(i)),text=row['context'])],question=row['input'],language='English'),
        reference=row.get('answers'),source=dict(url=url,revision=revision,row=i,sha256=hashlib.sha256(data.read_bytes()).hexdigest(),path='legal.jsonl',document_characters=len(row['context'])),
        selection='first row with full context 5000..150000 characters; no truncation, no answer-based selection; not full multi-document benchmark'))
    print(json.dumps(dict(prepared=['solar','agentscourt','raptor','lightrag'],ultradomain_rows=len(rows),selected_row=i)))

if __name__=='__main__':main()
