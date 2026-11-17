"""Fetch Kondo et al. LKG released resources bytes at fixed commit; verify every Git blob.
No model requests, credentials, weights or inference. See download_manifest.json.
"""
import asyncio,hashlib,json
from pathlib import Path
from urllib.parse import quote
import httpx
HERE=Path(__file__).parent;ROOT=HERE.parents[2]
async def main():
    manifest=json.loads((HERE/'download_manifest.json').read_text(encoding='utf-8'))
    folder=ROOT/'paper/upstream_sources/legal_reasoning_paths';folder.mkdir(parents=True,exist_ok=True)
    results=[];semaphore=asyncio.Semaphore(8)
    async with httpx.AsyncClient(timeout=180,follow_redirects=True) as client:
        async def fetch(entry):
            async with semaphore:
                path=(folder/entry['path']).resolve();path.relative_to(folder.resolve())
                try:
                    url='https://raw.githubusercontent.com/rkondo3/CapturingLegalReasoningPaths/'+manifest['commit']+'/'+quote(entry['path'],safe='/')
                    if path.is_file():data=path.read_bytes()
                    else:
                        response=await client.get(url);response.raise_for_status();data=response.content
                    blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
                    if blob!=entry['git_blob']:raise ValueError('Git blob differs: '+entry['path'])
                    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
                    return dict(path=entry['path'],sha256=hashlib.sha256(data).hexdigest(),git_blob=blob,bytes=len(data),status='verified')
                except Exception as error:return dict(path=entry['path'],status='failed',error=type(error).__name__+': '+str(error))
        results=await asyncio.gather(*(fetch(e) for e in manifest['files']))
    (HERE/'source_fetch_results.json').write_text(json.dumps(dict(commit=manifest['commit'],files=results),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    failed=[r for r in results if r['status']!='verified'];print(json.dumps(dict(files=len(results),verified=len(results)-len(failed),failed=failed,model_requests=0)))
    if failed:raise SystemExit(1)
    lock=HERE.parent/'sources.lock.json';entries=json.loads(lock.read_text(encoding='utf-8'))
    existing=next((s for s in entries if s['name']=='legal_reasoning_paths'),None)
    source=dict(name='legal_reasoning_paths',repository=manifest['repository'],commit=manifest['commit'],version=manifest['version'],local_path='paper/upstream_sources/legal_reasoning_paths',retrieval='verified_fixed_commit_download',files={r['path']:r['sha256'] for r in results})
    if existing and existing!=source:raise ValueError('Existing source entry differs; preserved')
    if not existing:entries.append(source);lock.write_text(json.dumps(entries,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':asyncio.run(main())
