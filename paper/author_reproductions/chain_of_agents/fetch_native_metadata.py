import requests,json;urls=['https://datasets-server.huggingface.co/rows?dataset=THUDM%2FLongBench&config=hotpotqa&split=test&offset=0&length=1','https://huggingface.co/api/datasets/THUDM/LongBench'];from pathlib import Path
for i,url in enumerate(urls):
 try:
  r=requests.get(url,timeout=20);print(json.dumps(dict(url=url,status=r.status_code,bytes=len(r.content),prefix=r.text[:120])),flush=True)
  if r.ok:Path('paper/author_reproductions/chain_of_agents/native_inputs/'+('longbench_row_response.json' if i==0 else 'longbench_hf_repository.json')).write_bytes(r.content)
 except Exception as e:print(type(e).__name__+': '+str(e),flush=True)
