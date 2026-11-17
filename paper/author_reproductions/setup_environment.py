"""Rebuild/check isolated environments for the implemented author adapters.

No model requests. Existing source changes are preserved and reported, never reset.
Only pinned repositories and files from sources.lock.json are checked out.
"""
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys

REPO=Path(__file__).resolve().parents[2]
BASE=REPO/'product_v1/.conda/screenshotlegal-v1/python.exe'
CONFIG={'legal_reasoning_paths':dict(folder='paper/.author_envs/legal_reasoning_paths',sources=['legal_reasoning_paths']),
        'graphrag':dict(folder='paper/.author_envs/graphrag',sources=['graphrag'],python='3.11'),
        'jurisma':dict(folder='paper/.author_envs/jurisma',sources=[]),
        'legalbench':dict(folder='paper/.author_envs/legalbench',sources=['legalbench','legalbench_data']),
        'ragchecker':dict(folder='paper/.author_envs/ragchecker',sources=['ragchecker','refchecker']),
        'self_refine':dict(folder='paper/.author_reproduction_env',sources=['self_refine','prompt_lib']),
        'react':dict(folder='paper/.author_envs/react',sources=['react']),
        'raptor':dict(folder='paper/.author_envs/raptor',sources=['raptor'],models=True),
        'lightrag':dict(folder='paper/.author_envs/lightrag',sources=['lightrag'],models=True),
        'reflexion':dict(folder='paper/.author_envs/reflexion',sources=['reflexion'],python='3.11'),
        'solar':dict(folder='paper/.author_envs/solar',sources=['solar','solar_legalbench'],python='3.13'),
        'agentscourt':dict(folder='paper/.author_envs/agentscourt',sources=['agentscourt']),
        'scale':dict(folder='paper/.author_envs/scale',sources=['scale']),
        'metagpt':dict(folder='paper/.author_envs/metagpt',sources=['metagpt'],python='3.11'),
        'lawbench':dict(folder='paper/.author_envs/lawbench',sources=['lawbench']),
        'legalagentbench':dict(folder='paper/.author_envs/legalagentbench',sources=['legalagentbench']),
        'chain_of_agents':dict(folder='paper/.author_envs/chain_of_agents',sources=['longbench']),
        'l_mad':dict(folder='paper/.author_envs/l_mad',sources=['mallm']),
        'paddleocr_vl':dict(folder='paper/.author_envs/paddleocr_vl',sources=[],model_lock='paddleocr_vl/model.lock.json')}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('method',choices=[*CONFIG,'all']);parser.add_argument('--check',action='store_true')
    args=parser.parse_args();lock=json.loads((Path(__file__).with_name('sources.lock.json')).read_text(encoding='utf-8'));by_name={s['name']:s for s in lock};reports=[]
    import hashlib
    selected=[name for name,c in CONFIG.items() if not c.get('models') and not c.get('model_lock')] if args.method=='all' else [args.method]
    if args.method!='all' and (CONFIG[args.method].get('models') or CONFIG[args.method].get('model_lock')) and not args.check:
        parser.error('Local neural-model branches are deferred by the user; only --check of existing resources is allowed')
    for name in selected:
        config=CONFIG[name];sources=[]
        for source_name in config['sources']:
            source=by_name[source_name];folder=(REPO/source['local_path']).resolve();folder.relative_to((REPO/'paper/upstream_sources').resolve())
            if source.get('retrieval')=='verified_fixed_commit_download':
                commit=source['commit']  # Identity fixed by public Git tree; every downloaded blob is independently verified.
            else:
                if not (folder/'.git').is_dir():
                    if args.check:raise ValueError('Missing pinned source: '+source_name)
                    folder.parent.mkdir(parents=True,exist_ok=True)
                    subprocess.run(['git','clone','--no-checkout','--depth','1','--filter=blob:none',source['repository'],str(folder)],check=True)
                    subprocess.run(['git','sparse-checkout','init','--no-cone'],cwd=folder,check=True)
                    patterns='\n'.join('/'+file for file in source['files'])+'\n'
                    subprocess.run(['git','sparse-checkout','set','--no-cone','--stdin'],input=patterns,text=True,cwd=folder,check=True)
                    subprocess.run(['git','fetch','--depth','1','origin',source['commit']],cwd=folder,check=True)
                    subprocess.run(['git','checkout','--detach',source['commit']],cwd=folder,check=True)
                commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=folder,text=True).strip()
                if commit!=source['commit']:raise ValueError('Existing source commit differs; preserved without checkout/reset: '+source_name)
            for file,sha in source['files'].items():
                target=folder/file
                if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest()!=sha:raise ValueError('Pinned source missing/changed; preserved: '+source_name+'/'+file)
            sources.append(dict(name=source_name,commit=commit,files_checked=len(source['files']),retrieval=source.get('retrieval','git_checkout')))
        environment=REPO/config['folder'];python=environment/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
        requirements=REPO/'paper/author_reproductions'/name/'requirements.lock.txt'
        if not args.check:
            if not python.is_file():
                base=BASE
                if config.get('python'):
                    version=config['python'];install_dir=REPO/'paper/.python'
                    candidates=list(install_dir.glob('cpython-'+version+'.*/python.exe')) if os.name=='nt' else list(install_dir.glob('cpython-'+version+'.*/bin/python3'))
                    if not candidates:
                        subprocess.run(['uv','python','install',version,'--install-dir',str(install_dir),'--no-bin','--no-registry','--cache-dir',str(REPO/'paper/.cache/uv')],check=True)
                        candidates=list(install_dir.glob('cpython-'+version+'.*/python.exe')) if os.name=='nt' else list(install_dir.glob('cpython-'+version+'.*/bin/python3'))
                    if not candidates:raise ValueError('Managed Python installation missing: '+version)
                    base=sorted(candidates)[-1]
                subprocess.run([str(base),'-m','venv','--without-pip',str(environment)],check=True)
            subprocess.run([str(BASE),'-m','pip','--python',str(python),'install','--index-url','https://pypi.org/simple','-r',str(requirements)],check=True)
        if not python.is_file():raise ValueError('Missing isolated Python: '+name)
        pins=dict(line.split('==',1) for line in requirements.read_text(encoding='utf-8').splitlines() if '==' in line and not line.startswith('#'))
        check='import json,importlib.metadata as m,sys;p=json.loads(sys.argv[1]);bad={k:[v,m.version(k)] for k,v in p.items() if m.version(k)!=v};print(json.dumps(dict(python=sys.version.split()[0],packages_checked=len(p),mismatches=bad)));sys.exit(bool(bad))'
        state=json.loads(subprocess.check_output([str(python),'-X','utf8','-B','-c',check,json.dumps(pins)],text=True))
        resources=[]
        if config.get('models'):
            if not args.check:subprocess.run([str(python),'-X','utf8','-B',str(Path(__file__).with_name('setup_local_models.py')),'embedding'],check=True)
            model_lock=json.loads((Path(__file__).with_name('local_models.lock.json')).read_text(encoding='utf-8'))
            model=model_lock['embedding']
            for file,sha in model['files'].items():
                target=REPO/model['path']/file
                if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest()!=sha:raise ValueError('Pinned local model missing/changed: '+file)
            resources.append(dict(name='embedding',revision=model['revision'],files_checked=len(model['files'])))
        if config.get('model_lock'):
            model_lock=json.loads((REPO/'paper/author_reproductions'/config['model_lock']).read_text(encoding='utf-8'))
            for file,data in model_lock['files'].items():
                target=REPO/'paper/.models/paddleocr_vl'/file
                with target.open('rb') as content:actual=hashlib.file_digest(content,'sha256').hexdigest()
                if actual!=data['sha256']:raise ValueError('Pinned original OCR model changed: '+file)
            resources.append(dict(name=model_lock['model'],revision=model_lock['revision'],files_checked=len(model_lock['files'])))
        report=dict(method=name,status='pinned_sources_and_environment_ready',model_requests=0,sources=sources,environment=state,resources=resources)
        (REPO/'paper/author_reproductions'/name/'environment_state.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');reports.append(report)
    print(json.dumps(reports,ensure_ascii=False))

if __name__=='__main__':main()
