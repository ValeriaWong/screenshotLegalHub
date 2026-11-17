import asyncio
import json
from screenshotlegal.settings import ROOT, Settings
from screenshotlegal.infrastructure.db.repository import Repository
from screenshotlegal.application.services.workspace import Workspace
from screenshotlegal.domain.common.models import CaseCreate, Selection, RunRequest

async def seed(workspace,owner_id=None):
    repo=workspace.repo
    demos=[c for c in repo.list('cases') if c['description']=='synthetic-demo-private-lending' and c.get('owner_id')==owner_id]
    if demos:
        return demos[0]
    case=workspace.create_case(CaseCreate(title='张三与李四 · 合成借贷演示',description='synthetic-demo-private-lending'),owner_id).model_dump()
    fixture=ROOT/'fixtures/demo_private_lending'
    data=json.loads((fixture/'fixture.json').read_text(encoding='utf-8'))
    mapping={}
    for page in (1,2):
        file=fixture/f'chat-{page}.png'
        evidence=workspace.upload(case['id'],file.name,'image/png',file.read_bytes())
        mapping[evidence.id]=[r for r in data['messages'] if r['page']==page]
    for name in ['张三','李四']:
        from screenshotlegal.domain.evidence.assessments import Party
        repo.put('parties',case['id']+name,Party(id=name,name=name).model_dump(),case['id'],immutable=True)
    await workspace.perceive(case['id'],'manual',mapping)
    workspace.select_matter(case['id'],Selection())
    workspace.compile(case['id'])
    run=workspace.start_run(case['id'],RunRequest())
    from screenshotlegal.runtime.review_gate import resolve_gate
    if not workspace.settings.auto_approve_gates:
        resolve_gate(repo,run['id'],'compile-review','approve')
    task=workspace.runtime.tasks.get(run['id'])
    if task:
        await task
    else:
        await workspace.runtime.execute(run['id'])
    finished=repo.get('analysis_runs',run['id'])
    if finished['status']!='COMPLETED':
        raise RuntimeError(finished)
    return repo.get('cases',case['id'])

def main():
    settings=Settings()
    workspace=Workspace(settings,Repository(settings.database_url))
    print(json.dumps(asyncio.run(seed(workspace)),ensure_ascii=False))

if __name__=='__main__':
    main()
