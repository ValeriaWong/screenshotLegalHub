"""LawLuo L02 upstream source parse probe; never executes or repairs author code.
Paper: https://arxiv.org/abs/2407.16252; identity: source_identity.json.
Original v3 method: case-graph RAG + four roles, fine-tuning/PPO.
This repository ToLC sketch is not verified as a complete v3 implementation.
Original I/O: informal legal consultation -> clarifying tree/dialogue/legal advice.
This file is an audit, not a reproduction or benchmark execution.
"""
import ast,hashlib,json
from pathlib import Path
HERE=Path(__file__).parent; ROOT=HERE.parents[2]
identity=json.loads((HERE/'source_identity.json').read_text(encoding='utf-8'))
path=ROOT/identity['local_path']; data=path.read_bytes()
assert hashlib.sha256(data).hexdigest()==identity['sha256']
assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==identity['original_git_blob']
result=dict(paper_id='L02',source_identity=identity,model_requests=0,source_unchanged=True,author_code_executed=False)
try:ast.parse(data.decode('utf-8'),filename=identity['original_path']);result['parse_passed']=True
except SyntaxError as error:result.update(parse_passed=False,syntax_error=dict(line=error.lineno,offset=error.offset,message=error.msg,text=error.text))
result['unimplemented_returns']=[line.strip() for line in data.decode('utf-8').splitlines() if line.strip().startswith('return ')]
(HERE/'source_probe.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(dict(parse_passed=result['parse_passed'],model_requests=0,source_unchanged=True)))
