"""Read model catalogs using authorized existing project credentials. No key output."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import json
import sys
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from legalhub.providers import sources

ENDPOINTS = {'siliconflow':'https://api.siliconflow.cn/v1',
             'moonshot':'https://api.moonshot.cn/v1','openai':'https://api.openai.com/v1'}


def probe(provider):
    candidates = sources(provider)
    result = {'provider':provider,'base_url':ENDPOINTS[provider],
              'available_credential_count':len(candidates),'attempts':[]}
    for ref,key in candidates[:3]:
        try:
            response = requests.get(ENDPOINTS[provider]+'/models',
                                    headers={'Authorization':'Bearer '+key},timeout=(10,30))
            attempt = {'credential_source':ref,'http_status':response.status_code}
            result['attempts'].append(attempt)
            if response.status_code == 200:
                rows = response.json().get('data',[])
                ids = [x['id'] for x in rows]
                result.update(status='catalog_ok',credential_source=ref,
                              model_count=len(ids),model_ids=ids)
                break
            result['status'] = 'http_error'
            if response.status_code not in [401,403]: break
        except requests.RequestException as error:
            result['attempts'].append({'credential_source':ref,'error_type':type(error).__name__})
            result['status']='network_error';break
    if not candidates: result['status']='missing_credential'
    return result


def main():
    with ThreadPoolExecutor(max_workers=3) as pool:
        rows = list(pool.map(probe, ENDPOINTS))
    destination=ROOT/'reports/v1.0.0_provider_probe.json'
    destination.write_text(json.dumps({'checked_at':datetime.now(timezone.utc).isoformat(),
                                      'providers':rows},ensure_ascii=False,indent=2),encoding='utf-8')
    for row in rows:
        summary={k:v for k,v in row.items() if k!='model_ids'}
        summary['relevant_models']=[x for x in row.get('model_ids',[])
                                    if any(q in x.lower() for q in ['qwen3','kimi','moonshot','gpt-6.1'])]
        print(json.dumps(summary,ensure_ascii=True),flush=True)


if __name__=='__main__': main()
