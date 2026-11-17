"""Try each distinct archived SiliconFlow credential once on the latest Qwen VLM."""
from pathlib import Path
import json
import sys
import yaml

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from legalhub.providers import sources
from legalhub import benchmark as b
from run_vision_pilot import cohort,predict,RUN,CONFIG


def main():
    cfg=yaml.safe_load(CONFIG.read_text(encoding='utf-8'))
    model=next(x for x in cfg['models'] if x['name']=='sf_qwen38_thinking')
    task=next(x for x in cohort()[1] if x['track']=='classification')
    destination=RUN/'siliconflow-key-pool.json'
    rows=[];selected=None
    for ref,key in sources('siliconflow'):
        prediction=predict(model,key,task)
        row={'credential_source':ref,'prediction':prediction}
        rows.append(row)
        destination.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({'credential_source':ref,'status':prediction['status'],
                          'http_status':prediction.get('http_status'),'provider_error':prediction.get('provider_error')},ensure_ascii=True),flush=True)
        if prediction['status']=='ok':selected=ref;break
        if prediction.get('http_status') not in [401,402,403]:break
    if selected:
        for item in cfg['models']:
            if item['provider']=='siliconflow':item['credential_source']=selected
        CONFIG.write_text(yaml.safe_dump(cfg,allow_unicode=True,sort_keys=False),encoding='utf-8')
    print(json.dumps({'usable_siliconflow_key_found':bool(selected),'attempts':len(rows)}),flush=True)


if __name__=='__main__':main()
