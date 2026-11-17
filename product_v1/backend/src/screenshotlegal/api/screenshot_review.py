"""Authenticated screenshot panel endpoints, independent of user-workbench records."""
from fastapi import Request
from fastapi.responses import FileResponse
from screenshotlegal.research.screenshot_review import (ScreenshotReview, Dataset, SaveMessage, SaveItem, LockRequest, RestoreRequest, Contract, regen_draft)
from screenshotlegal.research.screenshot_sources import ScreenshotSources
from screenshotlegal.research.renderer import verified

class PrepareRequest(Contract):
    source_id: str

class InitializeRequest(PrepareRequest):
    fingerprint: str
    expected_version: int
    acknowledge_exclusions: bool = False

class RegenerationRequest(Contract):
    package: dict
    item_id: str
    name: str
    prompt_id: str
    model_id: str = "demo"
    idempotency_key: str

def register_screenshot_review(app,store,review):
    panel=ScreenshotReview(store)
    sources=ScreenshotSources(store,review)
    app.state.research['screenshot_review']=panel
    def owner(request):
        return request.state.user.id

    @app.get('/v1/review/screenshot-sources')
    def inventory(request:Request):
        return sources.inventory(owner(request))

    @app.post('/v1/review/screenshot-prepare')
    def prepare(request:Request,payload:PrepareRequest):
        return sources.prepare(owner(request),payload.source_id)[1]

    @app.post('/v1/review/screenshot-initialize')
    def initialize(request:Request,payload:InitializeRequest):
        return sources.initialize(owner(request),panel,payload.source_id,payload.fingerprint,payload.expected_version,payload.acknowledge_exclusions)

    @app.get('/v1/review/screenshot-panels/{dataset}')
    def state(dataset:Dataset,request:Request):
        return panel.public(panel.state(owner(request),dataset))

    @app.put('/v1/review/screenshot-panels/{dataset}/items/{item_id}/messages/{message_id}')
    def message(dataset:Dataset,item_id:str,message_id:str,request:Request,payload:SaveMessage):
        return panel.save_message(owner(request),dataset,item_id,message_id,payload)

    @app.put('/v1/review/screenshot-panels/{dataset}/items/{item_id}')
    def item_review(dataset:Dataset,item_id:str,request:Request,payload:SaveItem):
        return panel.save_item(owner(request),dataset,item_id,payload)

    @app.get('/v1/review/screenshot-panels/{dataset}/items/{item_id}/image')
    def image(dataset:Dataset,item_id:str,request:Request):
        state=panel.state(owner(request),dataset)
        item=panel.item(state,item_id)
        return FileResponse(verified(store.root,item['asset']),media_type=item['asset']['mime_type'])

    @app.get('/v1/review/screenshot-panels/{dataset}/items/{item_id}/original')
    def original(dataset:Dataset,item_id:str,request:Request):
        return panel.item(panel.state(owner(request),dataset),item_id)['original_json']

    @app.get('/v1/review/screenshot-panels/B/items/{item_id}/regen-draft')
    def draft(item_id:str,request:Request):
        state=panel.state(owner(request),'B')
        return dict(instruction=regen_draft(panel.item(state,item_id),state['message_reviews'].get(item_id,{}),state['item_reviews'].get(item_id)))

    @app.post('/v1/review/screenshot-panels/{dataset}/export')
    def export(dataset:Dataset,request:Request):
        return panel.export(owner(request),dataset)

    @app.post('/v1/review/screenshot-panels/{dataset}/lock')
    def lock(dataset:Dataset,request:Request,payload:LockRequest):
        return panel.lock(owner(request),dataset,payload)

    @app.post('/v1/review/screenshot-panels/{dataset}/restore')
    def restore(dataset:Dataset,request:Request,payload:RestoreRequest):
        return panel.restore(owner(request),dataset,payload)

    @app.post('/v1/studio/screenshot-regenerate',status_code=201)
    def regenerate(request:Request,payload:RegenerationRequest):
        from screenshotlegal.research.screenshot_regeneration import create_regeneration
        return create_regeneration(app.state.research['studio'],owner(request),payload)

    @app.get('/v1/studio/screenshot-regen-package')
    def regen(request:Request):
        return panel.regen(owner(request))
