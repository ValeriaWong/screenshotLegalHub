from fastapi import Request,Query
from fastapi.responses import Response
from screenshotlegal.experiments.contracts import ExperimentCreate
from screenshotlegal.experiments.service import AgentExperiments
from screenshotlegal.research.contracts import dumps
from screenshotlegal.method_reproductions.catalog import METHOD_MODULES

def register_agent_evaluation(app,workspace,store,gateway,worker):
    service=AgentExperiments(store,workspace,app.state.auth,gateway,app.state.documents)
    worker.agent_experiments=service;app.state.research['agent_experiments']=service
    @app.get('/v1/evaluation/agent-methods')
    def methods():return service.registry.public()
    @app.post('/v1/evaluation/agent-preview')
    def preview(request:Request,payload:ExperimentCreate):return service.preview(request.state.user,payload)
    @app.post('/v1/evaluation/agent-runs',status_code=201)
    def create(request:Request,payload:ExperimentCreate):return service.create(request.state.user,payload)
    @app.get('/v1/evaluation/agent-runs')
    def runs(request:Request):return service.rows(request.state.user)
    @app.get('/v1/evaluation/agent-comparison')
    def compare(request:Request,ids:str=Query(min_length=1,max_length=3000)):return service.compare(request.state.user,ids.split(','))
    @app.get('/v1/evaluation/agent-runs/{id}')
    def result(id:str,request:Request):return service.result(request.state.user,id)
    @app.get('/v1/evaluation/agent-runs/{id}/export')
    def export(id:str,request:Request):
        result=service.result(request.state.user,id)
        name=METHOD_MODULES[result['run']['method']['id']]
        return Response(dumps(result),media_type='application/json',headers={'Content-Disposition':f'attachment; filename="{name}.{id}.json"'})
