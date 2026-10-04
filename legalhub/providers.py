"""Resolve existing project credentials without copying secrets into new configs."""
from pathlib import Path
import os
import yaml

ROOT = Path(__file__).resolve().parents[1]


def credential(ref):
    path = (ROOT/ref['path']).resolve()
    if ROOT not in path.parents:
        raise ValueError('Credential source must stay in the project')
    if ref.get('env_name'):
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            name, sep, value = line.strip().partition('=')
            if sep and name == ref['env_name']:
                return value.strip().strip('\"').strip("'")
        return ''
    cfg = yaml.safe_load(path.read_text(encoding='utf-8-sig'))
    model = next(x for x in cfg['models'] if x['name'] == ref['alias'])
    if 'key_index' in ref:
        return model['api_keys'][ref['key_index']]
    return model.get('api_key', '') or ''


def sources(provider):
    found = []
    if provider == 'openai':
        if os.environ.get('OPENAI_API_KEY'):
            found.append(({'environment': 'OPENAI_API_KEY'}, os.environ['OPENAI_API_KEY']))
        for name in ['configs/openai.local.env','projects/Batch/.env']:
            path = ROOT/name
            if path.exists():
                ref = {'path': name, 'env_name':'OPENAI_API_KEY'}
                found.append((ref, credential(ref)))
    hostname = {'siliconflow':'api.siliconflow.cn','moonshot':'api.moonshot.cn','openai':'api.openai.com'}[provider]
    from urllib.parse import urlsplit
    for name in ['projects/quiz-collector/config_full.yaml',
                 'projects/ScreenshotLegalBench_v2/process_local_evaluator/config.yaml',
                 'projects/ScreenshotLegalBench_v2/generate_chat/config_full.yaml',
                 'projects/llm_evluator/config.yaml']:
        path = ROOT/name
        if not path.exists(): continue
        cfg = yaml.safe_load(path.read_text(encoding='utf-8-sig'))
        for model in cfg.get('models',[]):
            if urlsplit(model.get('base_url','')).hostname == hostname:
                found.append(({'path': name, 'alias': model['name']}, model.get('api_key','')))
                for index,key in enumerate(model.get('api_keys') or []):
                    found.append(({'path':name,'alias':model['name'],'key_index':index},key))
    unique = []; seen = set()
    for ref, key in found:
        if key and key not in seen:
            seen.add(key); unique.append((ref,key))
    return unique
