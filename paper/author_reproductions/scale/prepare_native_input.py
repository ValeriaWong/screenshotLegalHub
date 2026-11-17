"""Use the first original case, retain both supplied article labels; no gold judgment exists in this CSV."""
import csv,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
path=ROOT/'paper/upstream_sources/scale/cases/cases_new_hudoc_001-231088.csv'
with path.open(encoding='utf-8-sig',newline='') as f:row=next(csv.DictReader(f))
value=dict(input=dict(mode='native',facts=row['Case'],articles=json.loads(row['Articles'])),source=dict(path=path.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),row=0,case_id=row['files']),gold_provided=False,prebuilt_author_hierarchy=True,parameter_adaptation='Original Stage 3/4 and iterative ReasoningStage with published master hierarchies; DeepSeek replaces original Qwen/Llama; no clipping of case facts or articles')
(ROOT/'paper/author_reproductions/native_inputs/scale.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(case=row['files'],articles=value['input']['articles'],case_characters=len(row['Case']))))
