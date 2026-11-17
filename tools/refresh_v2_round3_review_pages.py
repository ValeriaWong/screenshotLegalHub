"""Refresh review pages and tasks without changing messages or approved PNGs."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.v2_cause_batch import OUT,read,processing_items,case_review
from tools.build_v2_judgment_review import build
count=0
for item in processing_items():
    d=OUT/'zh'/item['id']
    if read(d/'status.json')['phase']!='rendered':continue
    build(d,read(d/'source.verification.json'))
    case_review(d,read(d/'case.json'),read(d/'render.json'));count+=1
print({'review_pages_refreshed':count,'images_regenerated':0})
