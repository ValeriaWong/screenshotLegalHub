import collections,json,tomllib
from pathlib import Path
r=Path(r'D:/workspace/screenshotLegalHub');p=r/'paper/upstream_sources/graphrag/poetry.lock';d=tomllib.loads(p.read_text(encoding='utf-8'));by={}
for v in d['package']:by.setdefault(v['name'],set()).add(v['version'])
assert all(len(v)==1 for v in by.values()),'Multiple locked versions need review'
g=r/'paper/author_reproductions/graphrag';(g/'author_constraints.txt').write_text('\n'.join(k+'=='+next(iter(v)) for k,v in sorted(by.items()))+'\n',encoding='utf-8');(g/'requirements.in').write_text('graphrag==0.1.1\n',encoding='utf-8');print(json.dumps(dict(author_locked_packages=len(by))))
