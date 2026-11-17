from pathlib import Path
import ast,io,tokenize,json,hashlib,stat,re
H=Path(__file__).resolve().parents[1]
M=H/'migration_manifest.json'
manifest=json.loads(M.read_text(encoding='utf-8'));names=manifest['projects']
def map_value(value):
 norm=re.sub(r'/+','/',value.replace('\\','/'))
 for name in names:
  for prefix in ['D:/workspace/'+name,'/home/allen/code/'+name,'/Users/macos/Downloads/workspace/'+name]:
   if norm==prefix or norm.startswith(prefix+'/'):return name,norm[len(prefix):].lstrip('/')
 prefix='/Users/macos/Downloads/workspace/kie_vqa_multichoice'
 if norm==prefix or norm.startswith(prefix+'/'):return 'quiz-collector',norm[len(prefix):].lstrip('/')
 if norm=='/home/allen/data/layout_vqa_case_text_only_merged.json':return 'quiz-collector','layout_vqa_case_text_only_merged.json'
 return None
new_changes=[];errors=[]
for name in names:
 for p in (H/'projects'/name).rglob('*.py'):
  raw=p.read_bytes()
  try:encoding,_=tokenize.detect_encoding(io.BytesIO(raw).readline);text=raw.decode(encoding);tree=ast.parse(text)
  except Exception as e:errors.append({'file':p.relative_to(H).as_posix(),'error':str(e)});continue
  lines=text.splitlines(keepends=True);offsets=[0]
  for line in lines:offsets.append(offsets[-1]+len(line))
  parents={child:node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
  def index(row,col):return offsets[row-1]+len(lines[row-1].encode('utf-8')[:col].decode('utf-8'))
  edits=[];refs=[]
  for node in ast.walk(tree):
   if not isinstance(node,ast.Constant) or not isinstance(node.value,str):continue
   if isinstance(parents.get(node),ast.JoinedStr):continue
   mapped=map_value(node.value)
   if mapped:
    edits.append((index(node.lineno,node.col_offset),index(node.end_lineno,node.end_col_offset),'_hub_project_path('+repr(mapped[0])+', '+repr(mapped[1])+')'))
    refs.append({'project':mapped[0],'relative':mapped[1],'exists':(H/'projects'/mapped[0]/mapped[1]).exists()})
  if not edits:continue
  for a,b,v in sorted(edits,reverse=True):text=text[:a]+v+text[b:]
  if 'from hub_paths import project_path as _hub_project_path' not in text:
   pos=0;body=tree.body
   if body and isinstance(body[0],ast.Expr) and isinstance(body[0].value,ast.Constant) and isinstance(body[0].value.value,str):pos=body[0].end_lineno
   for node in body:
    if isinstance(node,ast.ImportFrom) and node.module=='__future__':pos=max(pos,node.end_lineno)
   if pos==0:
    for i,line in enumerate(lines[:2]):
     if line.startswith('#!') or re.search('coding[:=]',line):pos=i+1
   depth=len(p.relative_to(H).parts)-1
   boot='\n# Added by screenshotLegalHub: resolve copied paths locally.\nfrom pathlib import Path as _HubPath\nimport sys as _hub_sys\n_HUB_ROOT = _HubPath(__file__).resolve().parents['+str(depth)+']\nif str(_HUB_ROOT) not in _hub_sys.path:\n    _hub_sys.path.insert(0, str(_HUB_ROOT))\nfrom hub_paths import project_path as _hub_project_path\n\n'
   lines2=text.splitlines(keepends=True);lines2.insert(pos,boot);text=''.join(lines2)
  compile(text,str(p),'exec');p.chmod(p.stat().st_mode|stat.S_IWRITE);p.write_bytes(text.encode(encoding));new_changes.append({'file':p.relative_to(H).as_posix(),'references':refs})
p=H/'projects/silicon-pool/docker-compose.yml';text=p.read_text(encoding='utf-8-sig').replace('"D:/silicon-pool:/app"','".:/app"');p.chmod(p.stat().st_mode|stat.S_IWRITE);p.write_text(text,encoding='utf-8')
for p in (H/'reports/ScreenshotLegalBench_v2').glob('*.md'):
 text=p.read_text(encoding='utf-8-sig')
 for name in names:text=text.replace('](D:/workspace/'+name+'/','](../../projects/'+name+'/')
 p.chmod(p.stat().st_mode|stat.S_IWRITE);p.write_text(text,encoding='utf-8-sig')
# Reconcile all already applied changes against the original copy snapshot.
changes=[]
for entry in manifest['files']:
 p=H/entry['destination']
 if p.suffix.lower() not in {'.py','.md','.yaml','.yml'}:continue
 digest=hashlib.sha256(p.read_bytes()).hexdigest()
 if digest!=entry['copied_sha256']:
  detail=next((x for x in new_changes if x['file']==entry['destination']),{})
  changes.append({'file':entry['destination'],'new_sha256':digest,'change':'Hub path adaptation or report link adaptation',**detail})
manifest['path_changes']=changes;manifest['adaptation_errors']=errors;manifest['copy_file_count']=len(manifest['files']);manifest['copy_total_bytes']=sum(x['bytes'] for x in manifest['files'])
M.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'path_changed_files':len(changes),'newly_adapted':len(new_changes),'syntax_errors':errors},ensure_ascii=False),flush=True)
