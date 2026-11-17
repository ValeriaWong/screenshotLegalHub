from pathlib import Path
import json,hashlib,ast,re,time,io,tokenize,sys
H=Path(__file__).resolve().parents[1];M=json.loads((H/'migration_manifest.json').read_text(encoding='utf-8'));R=Path(M['source_root']);modified={x['file']:x['new_sha256'] for x in M['path_changes']};errors=[];source_checked=destination_checked=0;last=None
for e in M['files']:
 group=e['source'].split('/')[0]
 if group!=last:print('VERIFY',group,flush=True);last=group
 a=R/e['source'];b=H/e['destination']
 if not a.is_file() or not b.is_file():errors.append({'missing':e['source']});continue
 def digest(p):
  h=hashlib.sha256()
  with p.open('rb') as stream:
   for chunk in iter(lambda:stream.read(4*1024*1024),b''):h.update(chunk)
  return h.hexdigest()
 actual=digest(a);source_checked+=1
 if actual!=e['copied_sha256']:errors.append({'source_changed_or_copy_mismatch':e['source']})
 expected=modified.get(e['destination'],e['copied_sha256']);actual=digest(b);destination_checked+=1
 if actual!=expected:errors.append({'destination_mismatch':e['destination']})
syntax=[];path_errors=[]
for p in (H/'projects').rglob('*.py'):
 try:
  raw=p.read_bytes();encoding,_=tokenize.detect_encoding(io.BytesIO(raw).readline);text=raw.decode(encoding);tree=ast.parse(text);compile(tree,str(p),'exec');syntax.append(p.relative_to(H).as_posix())
  for node in ast.walk(tree):
   if isinstance(node,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='_HUB_ROOT' for x in node.targets):
    if isinstance(node.value,ast.Subscript):
     idx=node.value.slice
     if isinstance(idx,ast.Index):idx=idx.value
     depth=ast.literal_eval(idx)
     if p.resolve().parents[depth]!=H.resolve():path_errors.append(p.relative_to(H).as_posix())
 except Exception as e:errors.append({'syntax_file':p.relative_to(H).as_posix(),'error':str(e)})
links=[]
for p in [H/'README.md',*(H/'projects').glob('*/启动说明.md'),*(H/'reports/ScreenshotLegalBench_v2').glob('*.md')]:
 text=p.read_text(encoding='utf-8-sig')
 for dest in re.findall(r'\]\(([^)]+)\)',text):
  if dest.startswith(('http:','https:','#')):continue
  clean=re.sub(r':\d+$','',dest);target=Path(clean) if re.match('[A-Za-z]:/',clean) else p.parent/clean
  if not target.exists():links.append({'document':p.relative_to(H).as_posix(),'target':dest})
missing_defaults=[]
for rel in ['projects/ScreenshotLegalBench_v2/process_local_evaluator/images','projects/llm_evluator/datasets','projects/quiz-collector/data/admin.jsonl','projects/ScreenshotLegalBench_v2/generate_chat/evaluate_prompts/scoring_prompt_v3.md','projects/ScreenshotLegalBench_v2/v2_eval_modelrefine']:
 if not (H/rel).exists():missing_defaults.append(rel)
# Only inspect the pure local path helper, without importing project services.
sys.path.insert(0,str(H));from hub_paths import project_path
for name in M['projects']:
 if Path(project_path(name))!=H/'projects'/name:errors.append({'helper_wrong_project':name})
result={'source_files_hash_verified':source_checked,'destination_files_hash_verified':destination_checked,'copied_files':len(M['files']),'copied_bytes':M['copy_total_bytes'],'copied_GiB':round(M['copy_total_bytes']/1024**3,3),'path_adapted_files':len(modified),'python_files_syntax_checked':len(syntax),'startup_docs':len(list((H/'projects').glob('*/启动说明.md'))),'source_project_directories_preserved':all((R/name).is_dir() for name in M['projects']),'errors':errors,'helper_root_errors':path_errors,'broken_document_links':links,'missing_existing_inputs':missing_defaults,'runtime_services_started':False,'dependencies_installed':False,'external_calls_made':False}
(H/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False),flush=True)
if errors or path_errors or links:raise SystemExit(1)
