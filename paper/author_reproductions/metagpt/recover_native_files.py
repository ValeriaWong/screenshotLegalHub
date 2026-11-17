"""Recover author-completed MetaGPT output after the adapter's UTF-8 collection failure.
No model calls/replays. The original failed record is retained; original Windows writes
used the locale encoding, while our Mermaid .mmd files explicitly used UTF-8.
"""
import ast,hashlib,json,locale,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'product_v1/backend/src'),str(ROOT)]
from paper.author_reproductions import run_per_paper_validation as shared
from screenshotlegal.research.contracts import digest,now
OUT=shared.OUT
author_environment=json.loads(subprocess.check_output([str(ROOT/'paper/.author_envs/metagpt/Scripts/python.exe'),'-c','import json,locale,sys; print(json.dumps(dict(encoding=locale.getpreferredencoding(False),utf8_mode=sys.flags.utf8_mode)))'],text=True))
original=OUT/'methods/e22_metagpt/runs/17679b90b3fee9e3__native'
plan=json.loads((original/'e22_metagpt.provenance.json').read_text(encoding='utf-8'))
request=json.loads((original/'e22_metagpt.input.json').read_text(encoding='utf-8'))
trace=json.loads((original/'e22_metagpt.model_responses.json').read_text(encoding='utf-8'))
tools=json.loads((original/'e22_metagpt.tools.json').read_text(encoding='utf-8'))
assert len(trace)==18 and all(t['status']=='completed' for t in trace)
messages=[t['result'] for t in tools if t['action']=='metagpt.published_message']
assert [m['cause_by'] for m in messages[:4]]==['BossRequirement','WritePRD','WriteDesign','WriteTasks']
assert messages[-1]['role']=='Engineer' and 'main.py' in messages[-1]['content']
folder=Path(request['runtime'])/'workspace'
files={};encodings={};syntax={};hashes={}
for path in folder.rglob('*'):
    if not path.is_file():continue
    name=path.relative_to(folder).as_posix();raw=path.read_bytes()
    encoding='utf-8' if path.suffix=='.mmd' else author_environment['encoding']
    files[name]=raw.decode(encoding);encodings[name]=encoding;hashes[name]=hashlib.sha256(raw).hexdigest()
    if path.suffix=='.py':
        try:ast.parse(files[name],filename=name);syntax[name]=True
        except SyntaxError:syntax[name]=False
assert syntax and all(syntax.values())
recovery_id=digest(dict(original_plan=plan['plan_id'],collector=Path(__file__).read_text(encoding='utf-8'),hashes=hashes))[:16]
directory=OUT/'methods/e22_metagpt/runs'/(recovery_id+'__native')
if (directory/'e22_metagpt.record.json').exists():raise ValueError('Recovery record already exists; preserve it')
result=dict(event='result',method='metagpt',output=dict(messages=messages,files=files),calls=len(trace),source_commit='820fee5df6697b4e85e90c787940de111c3ed05b',
    author_entry='original startup/Team/Environment/Role/software actions completed in original run; only output collection recovered',
    original_complete_benchmark=False,local_model_inference=False,product_adaptation_completed=False,
    adaptations=['LLM replaced with parent AIPING DeepSeek; original software prompts/parsers','default long-term memory off','Mermaid source retained; graphics not rendered','isolated new output workspace; overwrite/delete escape refused'],
    adaptation_errata=['Original loader removed only the outer Tenacity wrapper. All 18 actual requests were distinct successful stages, with no retry observed; current loader fully unwraps and has a one-call failure test.'],
    artifact_recovery=dict(original_failed_record=str((original/'e22_metagpt.record.json').relative_to(ROOT)),new_supplier_requests=0,algorithm_rerun=False,encodings=encodings,raw_file_hashes=hashes),
    native_functional_tests='pending generated-code review and functional smoke checks')
shared.save(directory/'e22_metagpt.input.json',request)
shared.save(directory/'e22_metagpt.output.json',result)
shared.save(directory/'e22_metagpt.model_responses.json',trace)
shared.save(directory/'e22_metagpt.prompts.json',[dict(stage=t['stage'],messages=t['messages']) for t in trace])
shared.save(directory/'e22_metagpt.tools.json',tools)
shared.save(directory/'e22_metagpt.provenance.json',dict(plan_id=recovery_id,created_at=now(),original_source_provenance=plan,
    collector_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),encoding=author_environment['encoding'],new_supplier_requests=0))
(directory/'recover_native_files.py').write_bytes(Path(__file__).read_bytes())
checks=dict(author_controller_completed=True,all_software_stages_run=True,written_python_files=len(syntax),syntax=syntax,all_requests_completed=True,
    local_model_inference=False,artifact_recovery_without_inference=True,functional_task_validation='pending generated-code review',original_benchmark_score=None)
shared.save(directory/'e22_metagpt.test_results.json',dict(status='completed',checks=checks,original_complete_benchmark=False))
shared.save(directory/'e22_metagpt.record.json',dict(paper_id='A04',method='e22_metagpt',track='native',status='completed',plan_id=recovery_id,result=result,per_paper_requests_including_history=18))
print(json.dumps(dict(status='author_outputs_recovered',plan_id=recovery_id,files=list(files),python_files=len(syntax),new_supplier_requests=0)))
