"""Load the pinned author's own HotpotQA sample as in CotQA_context.ipynb."""
import hashlib
import json
from pathlib import Path
import sys
import joblib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from author_runtime import source,ROOT
folder,pin=source('reflexion')
path=folder/'hotpotqa_runs/data/hotpot-qa-distractor-sample.joblib'
data=joblib.load(path).reset_index(drop=True)
row=data.iloc[0]
articles=list(row['context']['title']);sentences=row['context']['sentences']
context='\n\n'.join(''.join(sentences[articles.index(title)]) for title in row['supporting_facts']['title'])
result=dict(input=dict(mode='native',question=row['question'],context=context,answer_key=row['answer'],attempts=2),
 source=dict(repository=pin['repository'],commit=pin['commit'],path=path.relative_to(folder).as_posix(),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),sample_rows=len(data),row=0),
 selection='First row of the original author sample; supporting context construction matches CotQA_context notebook; key used by native evaluator only')
out=ROOT/'paper/author_reproductions/native_inputs/reflexion.json';out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(rows=len(data),question=row['question'],context_characters=len(context))))
